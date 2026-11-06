# Risk Checklist สำหรับตรวจ migration

หมายเหตุสำคัญ: ข้อเท็จจริงเรื่องพฤติกรรมของ DB ในไฟล์นี้เขียนแบบ "โดยทั่วไป" เท่านั้น
พฤติกรรมจริงขึ้นกับชนิด เวอร์ชัน และการตั้งค่าของ DB ให้ตรวจเอกสารของเวอร์ชันที่ใช้จริงทุกครั้งก่อนสรุป

## 1. DATA LOSS (ปกติ HIGH)
- ลบคอลัมน์ (Django `RemoveField`, SQL `DROP COLUMN`)
- ลบตารางหรือโมเดล (Django `DeleteModel`, SQL `DROP TABLE`) ให้ถามว่ามีการย้ายข้อมูลไปที่อื่นก่อนหรือไม่
- ลดขนาดหรือเปลี่ยนชนิดคอลัมน์จนค่าถูกตัดหรือแปลงไม่ได้
- `ON DELETE CASCADE` ที่เพิ่งเพิ่ม (ลบแถวแม่แล้วแถวลูกหายตาม)

มาตรการ: ย้ายข้อมูลก่อน, สำรองตารางหรือคอลัมน์ไว้, แยกการลบเป็นขั้นหลัง deploy โค้ดที่เลิกใช้แล้ว

## 2. CONSTRAINT ON EXISTING DATA (รันไม่ผ่านเมื่อมีข้อมูลจริง)
- เพิ่มคอลัมน์ `NOT NULL` ที่ไม่มี default
- เพิ่ม FK แบบ `NOT NULL` ด้วย `default=None` (Django `preserve_default=False`) จะล้มถ้ามีแถวอยู่แล้ว
- เปลี่ยนคอลัมน์เป็น `NOT NULL` จะล้มถ้ามี NULL
- เพิ่ม `UNIQUE` จะล้มถ้ามีค่าซ้ำ
- เพิ่ม `FOREIGN KEY` จะล้มถ้ามีแถวกำพร้า (orphan)
- เพิ่ม `CHECK` จะล้มถ้ามีแถวไม่ตรงเงื่อนไข
- default คงที่ที่เติมให้แถวเดิม (เช่น วันเวลาคงที่) ทำให้ทุกแถวได้ค่าเดียวกัน ซึ่งอาจไม่ใช่ความตั้งใจ

ตัวอย่าง query ตรวจก่อนรัน (ปรับชื่อตารางและคอลัมน์ตามจริง):

```sql
-- UNIQUE: หาค่าซ้ำ (ผลที่ยอมรับได้ = 0 แถว)
SELECT email, COUNT(*) FROM users GROUP BY email HAVING COUNT(*) > 1;

-- NOT NULL: นับค่า NULL (ผลที่ยอมรับได้ = 0)
SELECT COUNT(*) FROM users WHERE phone IS NULL;

-- FOREIGN KEY: หาแถวกำพร้า (ผลที่ยอมรับได้ = 0 แถว)
SELECT c.id FROM child c
LEFT JOIN parent p ON p.id = c.parent_id
WHERE c.parent_id IS NOT NULL AND p.id IS NULL;

-- CHECK: หาแถวที่ไม่ตรงเงื่อนไข (ใส่เงื่อนไขเดียวกับ CHECK)
SELECT COUNT(*) FROM t WHERE NOT (amount >= 0);
```

โดยทั่วไป UNIQUE ยอมให้มี NULL ซ้ำได้ แต่ตรวจกับเอกสารของ DB ที่ใช้ และระวังเรื่อง
ตัวพิมพ์เล็กใหญ่ หรือช่องว่างท้ายค่า ที่ทำให้ "ซ้ำ" ในมุมธุรกิจแต่ไม่ซ้ำในมุม DB

## 3. LOCK / DOWNTIME (กระทบเมื่อตารางใหญ่)
โดยทั่วไป:
- PostgreSQL: `CREATE INDEX` ปกติบล็อกการเขียนตลอดการสร้าง ให้ใช้ `CONCURRENTLY`
  (Django: `AddIndexConcurrently` และตั้ง `atomic = False` ใน Migration)
- PostgreSQL: `SET NOT NULL` สแกนทั้งตารางและถือ lock แรง
- เพิ่ม FK / CHECK จะตรวจทั้งตาราง ลดผลกระทบด้วย `NOT VALID` แล้ว `VALIDATE CONSTRAINT` แยกขั้น
- เปลี่ยนชนิดคอลัมน์มักเขียนตารางใหม่ทั้งตาราง
- เพิ่มคอลัมน์พร้อม default ค่าคงที่ เร็วใน PostgreSQL 11 ขึ้นไป (ไม่ต้องเขียนตารางใหม่)
- MySQL / MariaDB: ตรวจว่า ALTER เป็น INSTANT / INPLACE / COPY ตามเวอร์ชันและชนิดคำสั่ง
- SQLite: ALTER จำกัด หลายคำสั่งถูกทำเป็นสร้างตารางใหม่แล้วคัดลอกข้อมูล
- การ UPDATE ทุกแถวใน transaction เดียวบนตารางใหญ่ ถือ lock แถวนาน และทำให้ตารางบวม (bloat)

มาตรการ: ทำช่วงโหลดต่ำ, แบ่งขั้น/แบ่ง batch, ใช้วิธี online ของ DB นั้น, ตั้ง lock timeout
ถ้าไม่ทราบขนาดตาราง ให้ถือเป็น MEDIUM และระบุว่าต้องรู้ขนาดตาราง

## 4. IRREVERSIBLE
- Django `RunPython` ไม่มี `reverse_code`, `RunSQL` ไม่มี `reverse_sql`
- สคริปต์ SQL ล้วนของ Flyway (versioned migration โดยทั่วไปไม่มี undo ในรุ่นฟรี ตรวจเวอร์ชันที่ใช้)
- การลบข้อมูลหรือคอลัมน์ (ย้อน schema ได้ แต่ข้อมูลไม่กลับมา)

ถ้าไม่มีทางถอย ให้เขียนว่า "ทางเดียวคือกู้จากสำรองข้อมูล"

## 5. DEPLOY ORDER
- ลบหรือเปลี่ยนชื่อคอลัมน์/ตาราง (`RemoveField`, `RenameField`, `RenameModel`) ทำให้โค้ดเก่าที่ยังรันอยู่ error
  จนกว่าโค้ดใหม่ deploy เสร็จ (โดยเฉพาะ rolling deploy)
- เพิ่มคอลัมน์ `NOT NULL` ที่โค้ดเก่าไม่รู้จัก ทำให้ INSERT จากโค้ดเก่าไม่ผ่าน
- เปลี่ยนความหมายของค่าในคอลัมน์เดิม

มาตรการ: expand -> deploy โค้ด -> contract
(เพิ่มของใหม่ก่อน, deploy โค้ดที่ใช้ได้ทั้งสองแบบ, แล้วค่อยลบของเก่าใน migration ถัดไป)

## 6. DATA INTEGRITY / อื่น ๆ
- ถอดหรือผ่อน unique / constraint เดิม
- default ที่ไม่อยู่ใน `choices` / enum ของฟิลด์
- migration เดียวรวม schema กับการย้ายข้อมูลขนาดใหญ่ (ควรแยกเป็นไฟล์)
- dependency หรือลำดับไฟล์ชนกัน (หลาย leaf node, เลขเวอร์ชันซ้ำ)

## 7. ที่ไม่ต้องตกใจ (ลด false positive)
- `CreateModel` / `CREATE TABLE` ของตารางใหม่ที่ว่าง และ index/constraint บนตารางนั้นในไฟล์เดียวกัน = OK
- `AlterModelOptions` (ordering, verbose_name) ไม่แตะ DB
- เปลี่ยน `choices` / `help_text` / `verbose_name` ไม่มี SQL จริง
