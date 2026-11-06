# รีวิว migration: fixtures/case4_irreversible_runpython.py

## สรุป

**ยังไม่ควร merge หรือ deploy ตามนี้** บน PostgreSQL ที่ตาราง `events` มีราว 30 ล้านแถว migration นี้มีปัญหา 3 ข้อหลัก

1. ย้อนกลับไม่ได้ เพราะ `RunPython` ไม่มี `reverse_code`
2. `UPDATE` ทั้งตารางในคำสั่งเดียวและ transaction เดียว
3. `AddIndex` แบบธรรมดาจะ lock การเขียนตารางระหว่างสร้าง index

ข้อ 2 และ 3 ส่งผลต่อ production โดยตรง

หมายเหตุ: ตรวจจากเนื้อไฟล์นี้อย่างเดียว ยังไม่เห็น `models.py`, constraint ของตาราง หรือ migration ก่อนหน้า ข้อที่ต้องเช็กเพิ่มจึงแยกไว้ท้ายรายงาน

---

## ปัญหาที่พบ (เรียงตามความรุนแรง)

### 1. [สูง] `RunPython` ไม่มี `reverse_code` ทำให้ migration ย้อนกลับไม่ได้

```python
migrations.RunPython(normalize_event_types),
```

ถ้ารัน `migrate analytics 0031` เพื่อ rollback Django จะ raise `IrreversibleError` ที่ operation นี้ และ rollback ผ่านจุดนี้ไปไม่ได้เลย แม้ `AddIndex` ที่อยู่ถัดมาจะย้อนได้ก็ตาม

ควรใส่ `migrations.RunPython.noop` เป็น `reverse_code` ให้ชัดเจน แต่ต้องรู้ว่า **การแปลงเป็นตัวพิมพ์เล็กสูญเสียข้อมูล** เพราะกู้ตัวพิมพ์ใหญ่-เล็กเดิมกลับมาไม่ได้ `noop` แค่ทำให้ rollback ผ่านได้ ไม่ได้คืนข้อมูล ถ้าต้องการกู้ข้อมูลได้จริง ให้ทำอย่างใดอย่างหนึ่ง

- backup ตารางหรือคอลัมน์ก่อนรัน
- เก็บค่าเดิมไว้ในคอลัมน์ชั่วคราวจนมั่นใจ

### 2. [สูง] `UPDATE` ทั้งตาราง 30 ล้านแถวใน statement เดียว

```python
Event.objects.update(event_type=Lower("event_type"))
```

Django migration บน PostgreSQL ห่อด้วย transaction (`atomic = True`) เป็นค่าเริ่มต้น ผลที่ตามมาคือ

- **ไม่มี WHERE** จึงเขียนใหม่ทุกแถว แม้แถวที่เป็นตัวพิมพ์เล็กอยู่แล้ว เพราะ MVCC ของ PostgreSQL สร้าง tuple ใหม่ให้ทุกแถวที่ถูก UPDATE ตารางจะบวมขึ้นประมาณเท่าตัวจนกว่า vacuum จะเก็บกวาด
- WAL เกิดเป็นปริมาณมาก ทำให้ replica lag และดิสก์เต็มได้
- transaction ยาวมาก จึงถือ row lock ค้างทุกแถวที่แก้ ทำให้ `UPDATE`/`DELETE` จากแอปที่ชนแถวเหล่านั้นต้องรอ และ autovacuum เก็บ dead tuple ไม่ได้ระหว่างที่ transaction ยังเปิดอยู่
- ถ้าล้มเหลวกลางทาง (timeout, ดิสก์เต็ม) จะ rollback ทั้งก้อน เสียเวลาที่ทำไปทั้งหมด

**แนวทางแก้**

- กรองเฉพาะแถวที่ต้องแก้ด้วย `.exclude(event_type=Lower("event_type"))`
- แบ่งทำเป็น batch ตามช่วง PK
- ตั้ง `atomic = False` เพื่อให้แต่ละ batch commit แยกกัน
- ถ้าตารางรับ write หนัก ให้พิจารณารันเป็น management command หรือ background job นอกช่วง deploy แทนการรันใน migration

### 3. [สูง] `AddIndex` แบบธรรมดาบล็อกการเขียนตาราง

`AddIndex` สร้างด้วย `CREATE INDEX` ธรรมดา ซึ่งถือ `SHARE` lock บนตาราง `events` ตลอดเวลาที่ build index การ `INSERT`/`UPDATE`/`DELETE` ทั้งหมดจะถูกบล็อก (อ่านยังได้) กับตาราง 30 ล้านแถว อาจนานหลายนาที ตาราง analytics events โดยทั่วไปมี write ตลอดเวลา ผลคือ request ที่เขียน event ค้างหรือ timeout

ให้ใช้ `AddIndexConcurrently` แทน:

```python
from django.contrib.postgres.operations import AddIndexConcurrently
```

ซึ่งบังคับให้ migration ต้องตั้ง `atomic = False` ข้อควรระวังคือ ถ้า build ล้มเหลว PostgreSQL จะทิ้ง index สถานะ `INVALID` ไว้ ต้อง `DROP INDEX` ก่อนแล้วรันใหม่

### 4. [กลาง] ผสม data migration กับ schema migration ไว้ไฟล์เดียวกัน

`RunPython` (DML) และ `AddIndex` (DDL) อยู่ใน migration เดียวกัน ทำให้เกิดปัญหา

- ถ้าอยู่ใน transaction เดียวกัน การทำ DDL ต่อจาก DML ปริมาณมากเสี่ยงชน error อย่าง `cannot ALTER TABLE ... because it has pending trigger events` เมื่อมี deferred constraint ค้าง (FK ของ Django เป็น `DEFERRABLE INITIALLY DEFERRED`) กรณีนี้ความเสี่ยงต่ำเพราะไม่ได้แก้คอลัมน์ FK แต่ก็ไม่ควรพึ่งโชค
- ถ้าตั้ง `atomic = False` ทั้งไฟล์ แล้วล้มเหลวกลางทาง migration จะค้างสถานะครึ่ง ๆ กลาง ๆ ซึ่งแก้และรันซ้ำยาก

**ควรแยกเป็น migration คนละไฟล์** ไฟล์ละหนึ่งหน้าที่

### 5. [กลาง] ไม่มีมาตรการกันข้อมูลใหม่ที่ยังเป็นตัวพิมพ์ผสม

ระหว่างและหลัง backfill แอปอาจยังเขียน `event_type` ตัวพิมพ์ใหญ่หรือผสมเข้ามาอยู่ ข้อมูลที่ normalize แล้วจะกลับมาไม่สะอาดอีก ควรแก้ที่ต้นทางด้วย (เช่น normalize ใน `save()`, serializer, หรือจุด ingest) และ deploy โค้ดนั้น **ก่อน** รัน backfill

---

## ข้อเสนอแก้ไข: แยกเป็น 2 ไฟล์

**`0032_normalize_event_types.py`**

```python
from django.db import migrations
from django.db.models import Max
from django.db.models.functions import Lower

BATCH_SIZE = 50_000


def normalize_event_types(apps, schema_editor):
    Event = apps.get_model("analytics", "Event")
    qs = Event.objects.using(schema_editor.connection.alias)
    max_pk = qs.aggregate(m=Max("pk"))["m"] or 0
    for start in range(0, max_pk + 1, BATCH_SIZE):
        (
            qs.filter(pk__gte=start, pk__lt=start + BATCH_SIZE)
            .exclude(event_type=Lower("event_type"))  # ข้ามแถวที่เป็นตัวพิมพ์เล็กอยู่แล้ว
            .update(event_type=Lower("event_type"))
        )


class Migration(migrations.Migration):
    atomic = False  # แต่ละ batch commit แยกกัน

    dependencies = [
        ("analytics", "0031_event_source"),
    ]

    operations = [
        # noop ทำให้ rollback ผ่านได้ แต่ไม่คืนตัวพิมพ์ใหญ่-เล็กเดิม
        migrations.RunPython(normalize_event_types, migrations.RunPython.noop),
    ]
```

**`0033_event_occurred_at_idx.py`**

```python
from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False  # จำเป็นสำหรับ CREATE INDEX CONCURRENTLY

    dependencies = [
        ("analytics", "0032_normalize_event_types"),
    ]

    operations = [
        AddIndexConcurrently(
            model_name="event",
            index=models.Index(
                fields=["occurred_at"],
                name="events_occurred_at_idx",
            ),
        ),
    ]
```

โค้ด batch ข้างบนสมมติว่า PK เป็นจำนวนเต็ม ถ้าเป็น UUID ต้องเปลี่ยนไปใช้ keyset pagination แทน

---

## สิ่งที่ต้องเช็กเพิ่ม (ยังไม่เห็นในไฟล์ที่ให้มา)

- **Unique constraint หรือ unique index ที่เกี่ยวกับ `event_type`** ถ้ามี การทำเป็นตัวพิมพ์เล็กอาจทำให้ค่าที่เคยต่างกัน เช่น `Click` กับ `click` ชนกันจน migration พัง ควร query ตรวจก่อนรัน
- **โค้ดและ query ที่พึ่งตัวพิมพ์เดิม** เช่น filter แบบ exact match, cache key, dashboard, หรือ index บน `event_type` ที่จะถูกอัปเดตตามไปด้วย
- **`Meta.indexes` ใน `models.py`** ต้องมี index `events_occurred_at_idx` ตรงกับ migration ไม่เช่นนั้น `makemigrations` จะสร้าง migration ส่วนต่างขึ้นมาอีก ชื่อ index ยาว 22 ตัวอักษร อยู่ในขีดจำกัด 30 ตัวของ Django
- **มี index บน `occurred_at` อยู่แล้วหรือไม่** (เช่น เป็นส่วนหนึ่งของ composite index) เพื่อไม่ให้สร้างซ้ำซ้อน
- **`lower()` ของ PostgreSQL ขึ้นกับ collation/locale ของฐานข้อมูล** ถ้ามีค่าที่ไม่ใช่ ASCII ผลอาจต่างจาก `str.lower()` ของ Python ควรสุ่มตรวจ
- ซ้อม migration บนข้อมูลสำเนาขนาดใกล้ production ก่อน เพื่อวัดเวลา ขนาด WAL และขนาดตารางที่บวมขึ้น

---

## ลำดับ rollout ที่แนะนำ

1. deploy โค้ดที่ normalize `event_type` เป็นตัวพิมพ์เล็กตอนเขียน
2. backup หรือยืนยันว่ามี point-in-time recovery
3. รัน `0032` (backfill แบบ batch) ในช่วง traffic ต่ำและเฝ้าดู replica lag
4. รัน `0033` (สร้าง index แบบ concurrent) แล้วตรวจว่า index ไม่เป็น `INVALID`
5. รัน `VACUUM (ANALYZE)` บนตารางหลัง backfill เพื่อเก็บกวาด dead tuple และอัปเดต statistics
