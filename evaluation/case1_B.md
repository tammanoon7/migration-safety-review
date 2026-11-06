## สรุป
- ไฟล์: `fixtures/case1_drop_without_copy.py` (depends on `billing.0017_order_status_index`) | เครื่องมือ/DB (สมมติฐาน): Django migration, น่าจะเป็น PostgreSQL (ผู้ใช้ไม่ได้ระบุชนิด/เวอร์ชัน DB, ขนาดตาราง และวิธี deploy จึงสมมติว่า deploy แบบ rolling ซึ่งเป็นกรณีที่เสี่ยงกว่า)
- ระดับรวม: **HIGH**
- คำแนะนำ: **อย่าเพิ่งรัน** จนกว่าจะทำข้อ 1-3 นี้
  1. เพิ่มขั้นตอนย้ายข้อมูลจาก `OldConfig` ไป `NewConfig` (ไฟล์นี้ไม่มี `RunPython` / `RunSQL` เลย จึงเท่ากับสร้างตารางใหม่ว่าง ๆ แล้วทิ้งตารางเก่าพร้อมข้อมูลทั้งหมด)
  2. ยืนยันว่าข้อมูลใน `order.legacy_ref` และ `order.internal_note` ไม่จำเป็นแล้ว และไม่มีโค้ด รายงาน หรือระบบอื่นอ่านอยู่ แล้วสำรองข้อมูลสองคอลัมน์นี้ไว้
  3. แยกการลบ (`DeleteModel`, `RemoveField` x2) ไปเป็น migration ถัดไปหลัง deploy โค้ดที่เลิกใช้ของเก่าแล้ว (expand/contract)
- ตรวจแล้ว 4 operation: HIGH 3, MEDIUM 0, LOW 0, OK 1

## ตารางความเสี่ยง
| # | Operation | หมวด | ระดับ | ปัญหา | วิธีลดความเสี่ยง |
|---|-----------|------|-------|-------|------------------|
| 1 | `CreateModel NewConfig` (บรรทัด 11-27) | - | OK | ตารางใหม่ที่ว่าง ไม่มีผลกับข้อมูลเดิม | ไม่ต้องทำอะไร |
| 2 | `DeleteModel OldConfig` (บรรทัด 28-30) | DATA LOSS, IRREVERSIBLE, DEPLOY ORDER | **HIGH** | ลบตาราง `OldConfig` ทั้งตารางรวมข้อมูล และในไฟล์นี้ไม่มี operation ย้ายข้อมูลไป `NewConfig` เลย (ชื่อไฟล์บ่งว่า "drop without copy" ตรงกับที่เห็น) ย้อน schema ได้แต่ข้อมูลไม่กลับมา และถ้าโค้ดเก่าที่ยังรันอยู่ (rolling deploy) ยังอ่านหรือเขียน `OldConfig` จะ error ทันทีที่ migration รันเสร็จ นอกจากนี้ถ้าตั้งใจให้ `NewConfig` มาแทน `OldConfig` โค้ดก็ต้องเปลี่ยนไปใช้ `NewConfig` ก่อนด้วย | ย้ายข้อมูลก่อน (ดูตัวอย่างโค้ดด้านล่าง), สำรองตาราง, deploy โค้ดที่ใช้ `NewConfig` ก่อน แล้วค่อยลบ `OldConfig` ใน migration ถัดไป ถ้าจริง ๆ แค่เปลี่ยนชื่อโมเดลให้ใช้ `RenameModel` แทนการสร้างใหม่แล้วลบ |
| 3 | `RemoveField order.legacy_ref` (บรรทัด 31-34) | DATA LOSS, IRREVERSIBLE, DEPLOY ORDER | **HIGH** | ลบคอลัมน์ `legacy_ref` ของตาราง `order` ข้อมูลทุกแถวหายถาวร ถอยด้วย `migrate` ย้อนจะได้แค่คอลัมน์ว่าง ไม่ได้ข้อมูลคืน และโค้ดเก่าที่ยังอ้างคอลัมน์นี้ (ORM, admin, serializer, raw SQL, รายงาน/BI) จะ error ระหว่าง rolling deploy ไฟล์นี้บอกไม่ได้ว่าค่าในคอลัมน์ยังมีความหมายทางธุรกิจหรือไม่ | ตรวจว่ามีข้อมูลและมีใครใช้ (query ด้านล่าง + ค้นโค้ด), สำรองคอลัมน์, ลบหลัง deploy โค้ดที่เลิกอ้างถึงแล้ว |
| 4 | `RemoveField order.internal_note` (บรรทัด 35-38) | DATA LOSS, IRREVERSIBLE, DEPLOY ORDER | **HIGH** | เหมือนข้อ 3 และ `internal_note` ชื่อบ่งว่าเป็นบันทึกที่คนพิมพ์เอง ซึ่งโดยทั่วไปทดแทนด้วยการคำนวณใหม่ไม่ได้ ถ้ามีข้อมูลแล้วลบ ถือว่ากู้ได้ทางเดียวคือจากสำรองข้อมูล | เหมือนข้อ 3 และถามเจ้าของข้อมูล (ฝ่ายบัญชี/ซัพพอร์ต) ก่อนว่าต้องเก็บหรือไม่ ถ้าต้องเก็บให้ export ออกไปก่อน |

หมายเหตุเรื่อง lock: โดยทั่วไปการลบคอลัมน์/ตารางต้องใช้ lock แรงในช่วงสั้น ๆ และอาจรอคิวหลัง transaction ยาวที่ค้างอยู่ได้ แต่ผลจริงขึ้นกับชนิดและเวอร์ชัน DB (เช่น MySQL/MariaDB ต้องดูว่าเป็น INSTANT / INPLACE / COPY) ไม่ทราบขนาดตาราง `order` จึงต้องรู้ขนาดตารางก่อนประเมินส่วนนี้ ให้ตรวจเอกสารของเวอร์ชันจริงและตั้ง `lock_timeout` ตอนรัน (ไม่เปลี่ยนระดับรวม เพราะทุกข้อเป็น HIGH อยู่แล้วจากเรื่องข้อมูลหาย)

## ตรวจข้อมูลก่อนรัน
ชื่อตารางและคอลัมน์ด้านล่างเป็นสมมติฐานตามค่าเริ่มต้นของ Django (`billing_oldconfig`, `billing_order`) และคอลัมน์ของ `OldConfig` ที่ไฟล์นี้ไม่ได้บอกไว้ ให้ปรับตามจริงก่อนรัน และรันแบบอ่านอย่างเดียวบนสำเนาหรือ read replica ถ้าทำได้

```sql
-- 1) OldConfig มีข้อมูลกี่แถว (ถ้ามากกว่า 0 แปลว่าต้องย้ายก่อนลบ; ผลที่ยอมรับได้ของ "ลบโดยไม่ย้าย" = 0 แถว)
SELECT COUNT(*) FROM billing_oldconfig;

-- 2) legacy_ref ยังมีค่าอยู่กี่แถว (ผลที่ยอมรับได้ = 0 หรือได้ยืนยันกับเจ้าของข้อมูลแล้วว่าทิ้งได้)
--    ถ้าเป็น CharField/TextField ให้นับค่าว่างด้วย: AND legacy_ref <> ''
SELECT COUNT(*) FROM billing_order WHERE legacy_ref IS NOT NULL AND legacy_ref <> '';

-- 3) internal_note ยังมีค่าอยู่กี่แถว (เกณฑ์เดียวกับข้อ 2)
SELECT COUNT(*) FROM billing_order WHERE internal_note IS NOT NULL AND internal_note <> '';

-- 4) ถ้าจะย้าย OldConfig ไป NewConfig: NewConfig.key เป็น UNIQUE และ max_length=100
--    หาค่า key ซ้ำใน OldConfig (ผลที่ยอมรับได้ = 0 แถว; ปรับชื่อคอลัมน์ "key" ตามของ OldConfig จริง)
SELECT key, COUNT(*) FROM billing_oldconfig GROUP BY key HAVING COUNT(*) > 1;

--    ระวัง "ซ้ำ" ในมุมธุรกิจแต่ไม่ซ้ำในมุม DB เช่น ตัวพิมพ์เล็กใหญ่หรือช่องว่างท้ายค่า
SELECT LOWER(TRIM(key)), COUNT(*) FROM billing_oldconfig GROUP BY 1 HAVING COUNT(*) > 1;

--    หา key ที่ยาวเกิน 100 ตัวอักษร (ผลที่ยอมรับได้ = 0 แถว ไม่งั้นย้ายแล้วค่าถูกตัดหรือ error)
SELECT COUNT(*) FROM billing_oldconfig WHERE LENGTH(key) > 100;
```

นอกจาก query ให้ค้นในโค้ดทุก repo/service ที่ใช้ DB เดียวกัน หา `OldConfig`, `legacy_ref`, `internal_note` (รวม admin, serializer, fixture, raw SQL, dashboard/BI, ETL)

## เช็กลิสต์ก่อนรัน
- [ ] สำรองข้อมูล/snapshot (อย่างน้อยตาราง `billing_oldconfig` และคอลัมน์ `legacy_ref`, `internal_note` ของ `billing_order`) และลองกู้คืนจริงสักครั้งว่าอ่านได้
- [ ] เพิ่มขั้นตอนย้ายข้อมูล `OldConfig` -> `NewConfig` และตรวจจำนวนแถวหลังย้ายให้ตรงกัน
- [ ] ยืนยันกับเจ้าของข้อมูลว่า `legacy_ref` และ `internal_note` ลบได้ (เป็นลายลักษณ์อักษร)
- [ ] ทดสอบบน staging ที่มีข้อมูลขนาดใกล้เคียงจริง รวมถึงทดสอบ `migrate` ย้อนกลับ
- [ ] ลำดับ deploy โค้ดกับ migration: deploy โค้ดที่ไม่อ้าง `OldConfig` / `legacy_ref` / `internal_note` ให้ครบทุก instance ก่อน แล้วค่อยรันขั้นลบ
- [ ] ช่วงเวลาที่ล็อกได้ / คนที่เฝ้า (ไม่ทราบขนาดตาราง `order` จึงควรทำช่วงโหลดต่ำและตั้ง lock timeout)
- [ ] ผู้ดูแลที่มีสิทธิ์เป็นผู้รัน migration เอง (รีวิวนี้เป็นข้อมูลส่งต่อ ไม่ได้รันคำสั่งใด ๆ กับ DB)

### ตัวอย่างแนวทางแก้ (เป็นข้อเสนอ ไม่ได้แก้ไฟล์จริง)
แบ่งเป็นสองขั้น (expand/contract)

ขั้นที่ 1 (expand): สร้าง `NewConfig` และคัดลอกข้อมูล ยังไม่ลบอะไร

```python
def copy_config(apps, schema_editor):
    OldConfig = apps.get_model("billing", "OldConfig")
    NewConfig = apps.get_model("billing", "NewConfig")
    # ปรับชื่อ field ตาม OldConfig จริง (ไฟล์นี้ไม่ได้บอกโครงสร้างของ OldConfig)
    batch = [
        NewConfig(key=o.key, value=o.value)
        for o in OldConfig.objects.all().iterator()
    ]
    NewConfig.objects.bulk_create(batch, batch_size=1000, ignore_conflicts=False)


class Migration(migrations.Migration):
    dependencies = [("billing", "0017_order_status_index")]
    operations = [
        migrations.CreateModel(name="NewConfig", fields=[...]),  # เหมือนเดิม
        migrations.RunPython(copy_config, reverse_code=migrations.RunPython.noop),
    ]
```

จากนั้น deploy โค้ดที่ใช้ `NewConfig` และเลิกอ้าง `OldConfig`, `legacy_ref`, `internal_note` ให้ครบทุก instance

ขั้นที่ 2 (contract): migration ถัดไป หลังผ่านช่วงสังเกตการณ์และมีสำรองแล้ว จึงค่อยใส่ `DeleteModel("OldConfig")` และ `RemoveField` ทั้งสองตัว

## แผนถอยกลับ
- ย้อน schema: โดยทั่วไป `DeleteModel` และ `RemoveField` ของ Django ย้อนได้ในระดับ schema (สั่ง migrate ย้อนไปที่ `0017_order_status_index` จะสร้าง `OldConfig` และสองคอลัมน์กลับมา **แบบว่างเปล่า**) และการย้อนจะลบตาราง `NewConfig` ซึ่งรวมข้อมูลที่เขียนเข้ามาหลังรัน migration นี้ด้วย
- ข้อมูลที่ถอยแล้วไม่กลับมา: ข้อมูลทุกแถวของ `OldConfig`, ค่าใน `order.legacy_ref` และ `order.internal_note` รวมถึงข้อมูลใน `NewConfig` ที่เกิดหลังรัน (ถูกลบตอนย้อน)
- ทางเดียวที่จะได้ข้อมูลคืนคือกู้จากสำรองข้อมูล ดังนั้นต้องสำรองและทดสอบกู้ก่อนรัน
- หมายเหตุ: ถ้า `legacy_ref` / `internal_note` เป็นคอลัมน์ NOT NULL ที่ไม่มี default การย้อน `RemoveField` อาจล้มเมื่อมีแถวอยู่ในตาราง (ไฟล์นี้ไม่แสดงนิยามของฟิลด์เดิม จึงยืนยันไม่ได้) ให้ทดสอบการย้อนบน staging

## สิ่งที่ไฟล์นี้บอกไม่ได้
- ขนาดและข้อมูลจริงของ `OldConfig` และตาราง `order` (จำนวนแถว, มีค่าใน `legacy_ref` / `internal_note` กี่แถว)
- โครงสร้างคอลัมน์ของ `OldConfig` จึงยืนยันไม่ได้ว่าข้อมูลย้ายเข้า `NewConfig` (key/value/updated_at) ได้ครบหรือไม่ และ `NewConfig` ตั้งใจให้มาแทน `OldConfig` จริงหรือเปล่า
- โค้ดที่ยังอ่านหรือเขียน `OldConfig`, `order.legacy_ref`, `order.internal_note` (ทุก service, admin, รายงาน, ETL, BI)
- นิยามเดิมของฟิลด์ที่ถูกลบ (null/default) ซึ่งมีผลต่อการย้อน migration
- ชนิดและเวอร์ชัน DB, การตั้งค่า lock timeout, และวิธี deploy จริง (ปิดระบบหรือ rolling)
- ข้อตกลงด้านธุรกิจ/กฎหมายเรื่องการเก็บข้อมูล (retention) ของ `internal_note` และ `legacy_ref`
- ลำดับ dependency ของ migration อื่น ๆ ใน app `billing` (ไม่ได้เห็นไฟล์อื่น จึงตรวจเรื่อง leaf node ชนกันไม่ได้) และไม่ได้ตรวจ CLAUDE.md / AGENTS.md ของโปรเจกต์ว่ามีข้อห้ามเรื่องการรัน migration หรือไม่
- ไฟล์นี้เป็นการตรวจแบบอ่านอย่างเดียว ตรวจครบ 4 operation แต่ไม่ได้รัน migration ใด ๆ ผลนี้จึงไม่ใช่การรับรองว่าปลอดภัย
