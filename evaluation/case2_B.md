## สรุป
- ไฟล์: fixtures/case2_notnull_fk_default_none.py | เครื่องมือ/DB (สมมติฐาน): Django migration, PostgreSQL (ไม่ทราบเวอร์ชัน ถือว่า 11 ขึ้นไป), deploy แบบ rolling, ไม่ทราบขนาดและจำนวนแถวของตาราง `item` และ `stage`
- ระดับรวม: HIGH
- คำแนะนำ: อย่าเพิ่งรัน จนกว่าจะแก้ข้อ 2 (AddField `item.base_contract`) ให้ไม่ล้มเมื่อมีข้อมูล และตัดสินใจข้อ 1 กับข้อ 3 ตามตารางด้านล่าง ไฟล์นี้ผมไม่ได้รันอะไรเลย อ่านและวิเคราะห์อย่างเดียว ผลนี้เป็นข้อมูลส่งต่อให้ผู้ดูแลที่เป็นคนรัน migration เอง
- ตรวจแล้ว 3 operation: HIGH 1, MEDIUM 2, LOW 0, OK 0

## ตารางความเสี่ยง
| # | Operation | หมวด | ระดับ | ปัญหา | วิธีลดความเสี่ยง |
|---|-----------|------|-------|-------|------------------|
| 1 | `RenameField` ตาราง `item` คอลัมน์ `old_name` -> `new_name` (บรรทัด 13-17) | DEPLOY ORDER | MEDIUM | โค้ดเก่าที่ยังรันอยู่จะอ้างชื่อ `old_name` แล้ว error จนกว่าโค้ดใหม่จะ deploy ครบทุก instance โดยเฉพาะ rolling deploy ส่วนตัว rename เองโดยทั่วไปเป็นการแก้ metadata เร็ว แต่ต้องขอ lock แรงชั่วขณะ และอาจรอคิวหลัง transaction ยาว ๆ ที่ค้างอยู่ (ตรวจเอกสารของ DB เวอร์ชันจริง) ไม่มีข้อมูลหาย | ถ้าแค่ต้องการเปลี่ยนชื่อฝั่ง Python ให้ใช้ `db_column="old_name"` เพื่อไม่แตะคอลัมน์จริง ถ้าต้องเปลี่ยนชื่อจริง ใช้ expand/contract (เพิ่มคอลัมน์ใหม่, เขียนสองที่, backfill, deploy โค้ด, ค่อยลบของเก่า) หรือยอมรับช่วงโค้ดเก่า/ใหม่ไม่ตรงกัน (ปิดระบบสั้น ๆ / deploy พร้อมกัน) และตั้ง `lock_timeout` |
| 2 | `AddField` `item.base_contract` เป็น `ForeignKey` NOT NULL ด้วย `default=None` และ `preserve_default=False` (บรรทัด 18-28, `default=None` บรรทัด 22, `preserve_default=False` บรรทัด 27) | CONSTRAINT ON EXISTING DATA, DEPLOY ORDER, LOCK/DOWNTIME | HIGH | ฟิลด์ไม่ได้ `null=True` และ `default=None` ไม่ได้ให้ค่าจริงกับแถวเดิม ถ้าตาราง `item` มีแถวอยู่แม้แถวเดียว คอลัมน์ `base_contract_id` จะเป็น NULL แล้วละเมิด NOT NULL ทำให้ migration ล้ม (โดยทั่วไป PostgreSQL แจ้งว่า column contains null values) ถ้าตารางว่างจึงจะผ่าน นอกจากนี้ `preserve_default=False` แปลว่า Django ไม่เก็บ default ไว้ใน schema หลัง migration โค้ดเก่าที่ INSERT `item` โดยไม่รู้จักคอลัมน์นี้จะ error (NOT NULL violation) ระหว่าง rolling deploy และ FK ตัวนี้โดยทั่วไปสร้าง index และตรวจ constraint ทั้งตาราง ซึ่งถ้าตารางใหญ่ (ไม่ทราบขนาด จึงถือเป็น MEDIUM ในส่วนนี้ ต้องรู้ขนาดตาราง) อาจบล็อกการเขียน | แบ่งเป็น 3 ขั้นแบบ expand/contract ดูตัวอย่างด้านล่างตาราง: (A) เพิ่ม FK แบบ `null=True` (B) backfill ด้วย `RunPython` เป็น batch พร้อม `reverse_code` และ deploy โค้ดที่เขียนค่านี้ทุกครั้ง (C) ตรวจว่าไม่มี NULL แล้วค่อย `AlterField` เป็น NOT NULL ถ้าจะใช้ default เป็นสัญญาจริง ๆ ต้องมี `BaseContract` ที่มีอยู่จริงมารับ และต้องยืนยันกับเจ้าของธุรกิจว่าทุก item เดิมควรผูกกับสัญญาเดียวกันได้ ถ้าตารางใหญ่ให้พิจารณาสร้าง index แบบ concurrently และเพิ่ม FK แบบ `NOT VALID` แล้ว validate แยกขั้น |
| 3 | `AlterField` `stage.status` เปลี่ยน `choices` และ `default="pending"` (บรรทัด 29-42, `default` บรรทัด 39) | DATA INTEGRITY | MEDIUM | `"pending"` ไม่อยู่ใน `choices` (มีแค่ draft, review, approved, closed) การเปลี่ยน `choices` และ `default` ใน Django ไม่สร้าง SQL จริงและไม่แก้แถวเดิม (ไม่กระทบ lock) แต่ทุกแถวใหม่ที่สร้างโดยไม่ส่ง `status` จะได้ค่านอก choices ซึ่ง DB ไม่ปฏิเสธ (ไม่มี CHECK) ส่วน `full_clean`/ModelForm/Admin จะไม่ผ่าน และโค้ดที่ filter หรือ switch ตามสถานะอาจไม่รู้จักค่านี้ นอกจากนี้ถ้า choices เดิมมีค่าที่ถูกตัดออกในรอบนี้ (ไฟล์ไม่แสดง choices เดิม) แถวเดิมจะมีค่านอก choices ระดับ MEDIUM เพราะผลกระทบขึ้นกับว่าโค้ดสร้าง `Stage` โดยไม่ส่ง status หรือไม่ (ถ้าส่งทุกที่อาจลดเหลือ LOW) | แก้ให้ `default` เป็นค่าใน choices (เช่น `"draft"`) หรือเพิ่ม `("pending", "Pending")` ใน choices ตามที่ธุรกิจต้องการ ก่อนรัน และตรวจค่าที่มีอยู่จริงด้วย query ด้านล่าง |

ตัวอย่างการแบ่งขั้นสำหรับข้อ 2 (เป็นข้อเสนอ ไม่ได้แก้ไฟล์ต้นฉบับ):

```python
# 00xx_item_base_contract_expand.py  (ขั้น A)
migrations.AddField(
    model_name="item",
    name="base_contract",
    field=models.ForeignKey(
        null=True,
        blank=True,
        on_delete=django.db.models.deletion.PROTECT,
        related_name="items",
        to="contracts.basecontract",
    ),
),

# 00xx_item_base_contract_backfill.py  (ขั้น B)
def backfill(apps, schema_editor):
    Item = apps.get_model("catalog", "Item")
    # ใส่ตรรกะหาสัญญาที่ถูกต้องของแต่ละ item แล้วอัปเดตเป็น batch
    # อย่า UPDATE ทุกแถวใน transaction เดียวบนตารางใหญ่

migrations.RunPython(backfill, reverse_code=migrations.RunPython.noop),

# 00xx_item_base_contract_not_null.py  (ขั้น C รันหลังตรวจว่าไม่มี NULL และโค้ดใหม่ deploy แล้ว)
migrations.AlterField(
    model_name="item",
    name="base_contract",
    field=models.ForeignKey(
        on_delete=django.db.models.deletion.PROTECT,
        related_name="items",
        to="contracts.basecontract",
    ),
),
```

หมายเหตุเรื่องการรวมไฟล์: ไฟล์นี้รวมงานสามเรื่องที่ไม่เกี่ยวกัน (เปลี่ยนชื่อคอลัมน์ `item`, เพิ่ม FK `item`, แก้ฟิลด์ `stage`) ควรแยกเป็นไฟล์ละเรื่อง จะได้ถอยและตรวจทีละเรื่องได้ ถ้ารันบน PostgreSQL โดยทั่วไป migration นี้ทำงานใน transaction เดียว ถ้าข้อ 2 ล้ม ข้อ 1 จะถูก rollback ด้วย แต่ถ้าเป็น MySQL/MariaDB ที่ DDL ไม่อยู่ใน transaction ข้อ 1 อาจถูก apply ไปแล้วและทิ้ง schema ครึ่ง ๆ กลาง ๆ

## ตรวจข้อมูลก่อนรัน
ชื่อตารางด้านล่างสมมติตามชื่อมาตรฐานของ Django (`catalog_item`, `catalog_stage`, `contracts_basecontract`) ให้ปรับตามจริง (query อ่านอย่างเดียว ผู้ดูแลเป็นคนรันเอง)

```sql
-- ข้อ 2: ตาราง item มีแถวหรือไม่ (ผลที่ยอมรับได้สำหรับไฟล์นี้ตามที่เขียนไว้ = 0 ถ้า > 0 migration จะล้ม)
SELECT COUNT(*) FROM catalog_item;

-- ข้อ 2: มีสัญญาให้ผูกหรือไม่ ก่อนวางแผน backfill (ผลที่ยอมรับได้ = มากกว่า 0 ถ้าจะใช้ default จริง)
SELECT COUNT(*) FROM contracts_basecontract;

-- ข้อ 2 หลัง backfill (ก่อนขั้น C): ต้องไม่มี NULL (ผลที่ยอมรับได้ = 0)
SELECT COUNT(*) FROM catalog_item WHERE base_contract_id IS NULL;

-- ข้อ 2 หลัง backfill: หาแถวกำพร้า (ผลที่ยอมรับได้ = 0 แถว)
SELECT i.id FROM catalog_item i
LEFT JOIN contracts_basecontract c ON c.id = i.base_contract_id
WHERE i.base_contract_id IS NOT NULL AND c.id IS NULL;

-- ข้อ 3: ค่า status ที่มีอยู่จริง ผลที่ยอมรับได้ = มีแต่ draft, review, approved, closed
SELECT status, COUNT(*) FROM catalog_stage GROUP BY status ORDER BY COUNT(*) DESC;

-- ข้อ 3: แถวที่ status อยู่นอก choices ใหม่ (ผลที่ยอมรับได้ = 0 หรือยืนยันแล้วว่ายอมรับ)
SELECT COUNT(*) FROM catalog_stage
WHERE status NOT IN ('draft', 'review', 'approved', 'closed');
```

ข้อ 1 (`RenameField`) ไม่มี query ข้อมูล แต่ให้ค้นโค้ด/raw SQL/report/สคริปต์ภายนอกที่ยังอ้าง `old_name` ของ `item` (ดูหัวข้อ "สิ่งที่ไฟล์นี้บอกไม่ได้")

## เช็กลิสต์ก่อนรัน
- [ ] สำรองข้อมูล/snapshot (อย่างน้อยตาราง `catalog_item` และ `catalog_stage`)
- [ ] ทดสอบบน staging ที่มีข้อมูลขนาดใกล้เคียงจริง และมีแถวใน `item` ด้วย (ถ้าทดสอบกับตารางว่าง ข้อ 2 จะผ่านแบบหลอกตา)
- [ ] แก้ข้อ 2 ตามแนวทาง expand/contract (หรือยืนยันเป็นลายลักษณ์อักษรว่า `catalog_item` ว่างจริงในทุก environment ที่จะรัน)
- [ ] ตัดสินใจข้อ 3: แก้ `default` ให้อยู่ใน choices หรือเพิ่ม `pending` ใน choices
- [ ] ลำดับ deploy โค้ดกับ migration: โค้ดที่ทนทั้งชื่อ `old_name`/`new_name` ก่อน หรือวางแผนปิดระบบสั้น ๆ และโค้ดเก่าต้อง INSERT `item` ได้ในช่วงที่คอลัมน์ `base_contract` ยังเป็น nullable
- [ ] ช่วงเวลาที่ล็อกได้ / คนที่เฝ้า / ตั้ง `lock_timeout`
- [ ] ตรวจเอกสารของ DB เวอร์ชันจริงเรื่อง lock ของ RENAME COLUMN, การสร้าง index และการเพิ่ม FK
- [ ] ผู้ดูแลที่เป็นคนรัน migration ยืนยันนโยบายของโปรเจกต์ (ไม่ให้ AI รัน)

## แผนถอยกลับ
- ถ้า migration ล้มกลางทางบน PostgreSQL: โดยทั่วไปทั้งไฟล์ถูก rollback เป็น transaction เดียว ไม่มีอะไรเปลี่ยน ให้แก้แล้วรันใหม่ (บน MySQL/MariaDB ต้องตรวจเองว่า operation ไหน apply ไปแล้ว)
- ถ้ารันสำเร็จแล้วอยากถอย: ทั้ง 3 operation ย้อนได้ในระดับ schema (Django ย้อน `AlterField`, `AddField`, `RenameField` ตามลำดับกลับ ผู้ดูแลเป็นคนสั่ง migrate กลับไปที่ `0024_item_stage` ของ app `catalog`)
- ข้อมูลที่ถอยแล้วไม่กลับมา: ค่าในคอลัมน์ `item.base_contract_id` ทั้งหมด (คอลัมน์ถูกลบตอนย้อน) ถ้ามี backfill แล้วต้องสำรองก่อน ส่วนข้อ 3 ไม่แก้ข้อมูลเดิม แต่แถวที่ถูกสร้างด้วย `"pending"` ระหว่างนั้นยังคงอยู่ในตาราง
- ถ้าข้อมูลเสียหายหรือถอยแบบ schema ไม่พอ ทางเดียวคือกู้จากสำรองข้อมูล
- ระหว่างที่ถอย โค้ดใหม่ที่อ้าง `new_name` หรือ `base_contract` จะ error จึงต้อง rollback โค้ดให้สอดคล้องกัน

## สิ่งที่ไฟล์นี้บอกไม่ได้
- จำนวนแถวและขนาดจริงของ `catalog_item`, `catalog_stage` (ข้อ 2 ล้มแน่ถ้า `item` มีแถว และผลกระทบเรื่อง lock ขึ้นกับขนาดตาราง)
- ชนิดและเวอร์ชัน DB จริง (ใช้สมมติฐาน PostgreSQL 11 ขึ้นไป) และการตั้งค่า เช่น `lock_timeout`, migration รันใน transaction หรือไม่
- วิธี deploy จริง (rolling หรือปิดระบบ) ซึ่งกำหนดน้ำหนักของความเสี่ยง DEPLOY ORDER ในข้อ 1 และ 2
- โค้ด/query/raw SQL/report/ETL/สคริปต์ภายนอกที่ยังอ้าง `item.old_name` หรือสร้าง `Item` โดยไม่มี `base_contract`
- โค้ดที่สร้าง `Stage` โดยไม่ส่ง `status` และโค้ดที่ branch ตามค่า `status` (รวมถึงรู้จักค่า `pending` หรือไม่)
- `choices` เดิมของ `stage.status` และค่าที่มีอยู่จริงในตาราง (ไฟล์เห็นเฉพาะสถานะใหม่)
- ตรรกะธุรกิจว่า `item` เดิมแต่ละตัวควรผูกกับ `BaseContract` ตัวไหน และมี `BaseContract` อยู่ในตารางหรือยัง
- ว่า dependency `("contracts", "0009_basecontract")` และ `("catalog", "0024_item_stage")` ถูกต้อง และไม่มี leaf node หลายตัวใน app `catalog` (ไฟล์เดียวตรวจไม่ได้)
- นโยบายของโปรเจกต์ (CLAUDE.md / AGENTS.md) เรื่องการให้ AI รัน migration ซึ่งผมไม่ได้เปิดดู จึงเขียนผลนี้เป็นข้อมูลส่งต่อให้ผู้ดูแลที่รันเอง
- ผมตรวจครบ 3 จาก 3 operation ในไฟล์นี้ แต่ไม่ถือว่าสรุปว่า "ปลอดภัย" ได้ จนกว่าจะตอบข้อด้านบนและแก้ข้อ 2
