# ผลตรวจ migration: `fixtures/case1_drop_without_copy.py`

**สรุป: ยังไม่ควร merge หรือ deploy ตามสภาพนี้**

migration นี้ลบข้อมูลถาวร 3 จุด คือตาราง `OldConfig` และคอลัมน์ `order.legacy_ref` กับ `order.internal_note` โดยไม่มีขั้นตอนคัดลอกหรือสำรองข้อมูลเลย ชื่อไฟล์ (`drop_without_copy`) ก็ตรงกับปัญหานี้พอดี

## ปัญหาที่พบ

### 1. (Critical) ลบ `OldConfig` โดยไม่ย้ายข้อมูลไป `NewConfig`

- `CreateModel("NewConfig")` แล้วตามด้วย `DeleteModel("OldConfig")` ทันที โดยไม่มี `RunPython` หรือ `RunSQL` คั่นกลาง
- `NewConfig` เป็นตารางว่าง ส่วนข้อมูลใน `OldConfig` ทั้งหมดจะหายไปเมื่อรัน migrate
- ถ้าความตั้งใจคือ "เปลี่ยนชื่อ/ปรับโครงสร้าง" ให้ใช้ `RenameModel` บวก `AlterField`/`AddField` ซึ่งเก็บข้อมูลไว้ได้ หรือเขียน data migration คัดลอกข้อมูลก่อนแล้วค่อยลบ
- ต้องตรวจด้วยว่ามีโมเดลอื่นมี FK ชี้ไป `OldConfig` หรือไม่ และโค้ดส่วนอื่นยัง import/อ้างถึงอยู่หรือไม่ บน PostgreSQL Django ใช้ `DROP TABLE ... CASCADE` ซึ่ง constraint จากตารางอื่นอาจถูกลบไปเงียบ ๆ

### 2. (High) `RemoveField` สองตัวบน `order` ทำให้ข้อมูลหาย และเสี่ยงล่มตอน rolling deploy

- `legacy_ref` และ `internal_note` ถูกลบพร้อมข้อมูลทั้งคอลัมน์ ไม่มีการเก็บไว้ที่ใด ยืนยันกับเจ้าของข้อมูลหรือฝ่ายที่เกี่ยวข้องก่อนว่าไม่ต้องใช้แล้วจริง
- ลำดับ deploy ปกติคือรัน migrate ก่อนแล้วโค้ดใหม่ค่อยขึ้น ช่วงนั้นโค้ดเก่าที่ยังรันอยู่จะ SELECT คอลัมน์เหล่านี้ และจะเจอ error แนว "column does not exist"
- ควรแยกเป็น 2 release ดังนี้
  - release แรก: เอาโค้ดที่อ่านหรือเขียนสองฟิลด์นี้ออกก่อน (ถ้าต้องการอาจใช้ `SeparateDatabaseAndState` ลบเฉพาะ state ก่อน)
  - release ถัดไป: ค่อยลบคอลัมน์จริง
- บนตารางใหญ่ ให้เช็กว่า DB ที่ใช้ลบคอลัมน์แบบ metadata-only หรือต้อง rebuild ทั้งตาราง (PostgreSQL เร็วและล็อกสั้น ส่วน MySQL บางเวอร์ชันอาจ rebuild) รวมถึงว่าสองฟิลด์นี้มี index หรือ constraint ผูกอยู่หรือไม่

### 3. (Medium) ย้อนกลับ (reverse) ได้แค่โครงสร้าง ข้อมูลไม่กลับมา

- reverse ของ `DeleteModel` จะสร้างตารางเปล่า ส่วน reverse ของ `RemoveField` จะเพิ่มคอลัมน์กลับมาโดยค่าเป็น NULL หรือค่า default
- ถ้าฟิลด์ใดเป็น NOT NULL และไม่มี default การ reverse จะล้มเหลว
- สรุปคือ rollback จริงทำไม่ได้ ต้องพึ่ง backup อย่างเดียว ควรมี backup หรือ snapshot ก่อน deploy และบันทึกไว้ใน PR ว่าตั้งใจให้ย้อนกลับไม่ได้

### 4. (Medium) รวมหลายเรื่องไว้ใน migration เดียว

- ตอนนี้มีทั้งสร้างโมเดลใหม่ ลบโมเดลเก่า และลบคอลัมน์สองตัวของตารางอื่นอยู่ในไฟล์เดียว
- ถ้าบางขั้นล้มกลางทางจะไล่ปัญหาและแก้ยาก ส่วน DB ที่ DDL ไม่อยู่ใน transaction ก็จะค้างครึ่ง ๆ กลาง ๆ
- แนะนำให้แยกไฟล์: (a) เพิ่ม `NewConfig` (b) คัดลอกข้อมูล (c) release ถัดไป ลบของเก่า
- ถ้า (a) กับ (b) อยู่ใน transaction เดียวกันบน PostgreSQL อาจเจอ error "pending trigger events" ให้แยกไฟล์จะปลอดภัยกว่า

### 5. (Low / ควรตรวจเพิ่ม) รายละเอียดของ `NewConfig`

- `key` เป็น `unique=True` และ `max_length=100` ถ้า `OldConfig` มี key ซ้ำหรือยาวเกิน 100 ตอนคัดลอกจะพัง ให้ตรวจข้อมูลจริงก่อน
- `updated_at` เป็น `auto_now=True` ซึ่งจะถูกเขียนทับเป็นเวลาปัจจุบันเมื่อคัดลอกผ่าน ORM (`save`/`bulk_create`) ถ้าต้องการเก็บเวลาเดิมให้ใช้ `RunSQL` หรือ `QuerySet.update()` ตั้งค่าหลังสร้าง
- `BigAutoField` ต้องสอดคล้องกับ `DEFAULT_AUTO_FIELD` และ `default_auto_field` ของแอป `billing` เพื่อไม่ให้ `makemigrations` สร้าง migration แก้ซ้ำภายหลัง

## แนวทางแก้ที่แนะนำ

**ไฟล์ที่ 1: สร้างตารางใหม่ แล้วคัดลอกข้อมูล (ยังไม่ลบอะไร)**

```python
from django.db import migrations, models


def copy_old_to_new(apps, schema_editor):
    OldConfig = apps.get_model("billing", "OldConfig")
    NewConfig = apps.get_model("billing", "NewConfig")
    # ชื่อฟิลด์ของ OldConfig ด้านล่างเป็นการสมมติ ต้องปรับให้ตรงกับของจริง
    batch = []
    for old in OldConfig.objects.all().iterator(chunk_size=1000):
        batch.append(NewConfig(key=old.key, value=old.value))
        if len(batch) >= 1000:
            NewConfig.objects.bulk_create(batch)
            batch.clear()
    if batch:
        NewConfig.objects.bulk_create(batch)


class Migration(migrations.Migration):
    dependencies = [("billing", "0017_order_status_index")]

    operations = [
        migrations.CreateModel(
            name="NewConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=100, unique=True)),
                ("value", models.TextField(blank=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.RunPython(copy_old_to_new, migrations.RunPython.noop),
    ]
```

**ไฟล์ที่ 2 (release ถัดไป หลังโค้ดเลิกใช้ของเก่าแล้วและตรวจข้อมูลครบ):** `DeleteModel("OldConfig")`

**ไฟล์ที่ 3 (release ถัดไป หลังโค้ดเลิกอ้าง `legacy_ref`/`internal_note` แล้ว และยืนยันว่าไม่ต้องเก็บข้อมูล):** `RemoveField` ทั้งสองตัว

## เช็กลิสต์ก่อน merge

- [ ] ยืนยันว่า `OldConfig` และสองฟิลด์ของ `order` ไม่มีโค้ดอ้างถึงแล้ว (grep ทั้ง repo รวม admin, serializer, report, task เบื้องหลัง)
- [ ] ไม่มี FK หรือ constraint จากที่อื่นชี้มาที่ `OldConfig`
- [ ] มี data migration ที่ทดสอบกับข้อมูลจริงหรือสำเนา production แล้ว และนับจำนวนแถวเทียบกันก่อน-หลัง
- [ ] มี backup/snapshot และแผนรับมือถ้าต้องย้อนกลับ
- [ ] เจ้าของข้อมูลอนุมัติการลบ `legacy_ref` และ `internal_note`
- [ ] แยก deploy เป็นหลาย release ตามที่เสนอ

หมายเหตุ: การตรวจนี้อิงจากเนื้อไฟล์ migration ที่ให้มาเท่านั้น ยังไม่ได้ดูนิยามโมเดล `OldConfig` / `Order` หรือโค้ดส่วนอื่นของโปรเจกต์ ข้อที่ระบุว่าให้ตรวจเพิ่มจึงต้องยืนยันกับของจริงอีกครั้ง
