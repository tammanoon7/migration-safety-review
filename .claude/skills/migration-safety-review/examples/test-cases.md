# ชุดทดสอบและเฉลย (Test cases + Answer key)

ไฟล์นี้มีเฉลย **ห้ามให้ AI ที่กำลังถูกทดสอบเห็น** (ทั้งฝั่ง AI ปกติและฝั่ง AI + Skill) และห้ามคัดลอกเฉลยไปไว้ใน `fixtures/`
ไฟล์ตัวอย่างอยู่ที่ `fixtures/` ที่ root ของโปรเจกต์ เป็นไฟล์ข้อความอย่างเดียว ไม่ต้องติดตั้งเฟรมเวิร์กและไม่ต้องรัน

## เฉลย

| Case | ไฟล์ | บริบทที่ให้ AI (อยู่ในไฟล์) | ความเสี่ยงที่ควรเจอ | ระดับตามเฉลย |
|------|------|------------------------------|----------------------|----------------|
| 1 | `case1_drop_without_copy.py` | Django migration ไม่ระบุ DB | R1.1 DATA LOSS: `DeleteModel OldConfig` และ `RemoveField` 2 คอลัมน์ของ `order` โดยไม่มี RunPython ย้ายข้อมูล | HIGH |
| | | | R1.2 DEPLOY ORDER: ลบโมเดล/คอลัมน์ ทำให้โค้ดเก่าที่ยังรันอยู่ error | MEDIUM |
| | | | `CreateModel NewConfig` (ตารางใหม่ว่าง) | OK |
| 2 | `case2_notnull_fk_default_none.py` | Django migration ไม่ระบุ DB | R2.1 CONSTRAINT: `AddField item.base_contract` เป็น FK NOT NULL ด้วย `default=None`, `preserve_default=False` ล้มถ้ามีแถว | HIGH |
| | | | R2.2 DEPLOY ORDER: `RenameField item.old_name -> new_name` | MEDIUM |
| | | | R2.3 DATA INTEGRITY: `stage.status` default `pending` ไม่อยู่ใน choices 4 ค่า | LOW |
| 3 | `case3_postgres_ddl.sql` | PostgreSQL 15, `orders` ประมาณ 50 ล้านแถว, deploy พร้อมโค้ดที่เลิกใช้ `users.phone` ในรอบเดียวกัน | R3.1 CONSTRAINT: `ADD COLUMN status ... NOT NULL` ไม่มี default บนตารางที่มีข้อมูล | HIGH |
| | | | R3.2 LOCK: `CREATE INDEX` ไม่ `CONCURRENTLY` บนตารางใหญ่ | MEDIUM-HIGH |
| | | | R3.3 DATA LOSS + DEPLOY ORDER: `DROP COLUMN users.phone` | HIGH |
| | | | R3.4 CONSTRAINT + LOCK: `ADD CONSTRAINT UNIQUE (email)` ล้มถ้ามีอีเมลซ้ำ และบล็อกการเขียน ต้องมี query หาค่าซ้ำ | HIGH หรือ MEDIUM |
| 4 | `case4_irreversible_runpython.py` | PostgreSQL, `events` ประมาณ 30 ล้านแถว | R4.1 IRREVERSIBLE: `RunPython` UPDATE ทุกแถวโดยไม่มี `reverse_code` | MEDIUM-HIGH |
| | | | R4.2 LOCK/DOWNTIME: `AddIndex` ปกติบนตารางใหญ่ | MEDIUM |
| | | | (แถม ไม่นับใน N) UPDATE ทุกแถวใน transaction เดียวถือ lock นาน | - |
| 5 | `case5_safe_control.sql` | PostgreSQL 15 | ทุก operation = OK (`CREATE TABLE` ใหม่ + index บนตารางนั้น) ห้ามมี HIGH | OK |

**N = 11** (ความเสี่ยงที่ควรเจอจาก case 1-4: case1 = 2, case2 = 3, case3 = 4, case4 = 2) ใช้เป็นตัวหารของคะแนน "เจอความเสี่ยง"
case 5 ไม่นับใน N ใช้วัด false positive อย่างเดียว

## เกณฑ์ตรวจเทียบเฉลย (ใช้ชุดเดียวกันทุกรอบ ทั้งฝั่ง A และ B)

1. **เจอความเสี่ยง** นับ 1 ต่อรายการ R ที่ระบุ operation นั้นและบอกประเภทปัญหาตรงกับเฉลย (ไม่ต้องตรงระดับ) ถ้าพูดกว้าง ๆ โดยไม่ชี้ operation ไม่นับ
2. **ชี้ operation ถูกตัว** ข้อที่นับว่าเจอ ต้องระบุชื่อ operation หรือตาราง/คอลัมน์ที่เกิดเรื่อง
3. **ระดับสมเหตุผล** ระดับที่ให้อยู่ในช่วงของเฉลย (เช่น MEDIUM-HIGH ยอมรับทั้ง MEDIUM และ HIGH) ถ้าความเสี่ยงนั้นถูกรวมไว้ใน operation เดียวกับความเสี่ยงอื่นที่เฉลยให้ HIGH และ operation นั้นถูกให้ HIGH ถือว่าตรง ถ้าห่างจากเฉลยหนึ่งระดับขึ้นไปนับว่า "ไม่ตรง" และจดไว้
4. **False positive (case 5)** นับจำนวนจุดที่ให้ HIGH หรือ MEDIUM กับ operation ที่เฉลยบอกว่า OK
5. **ให้ query ตรวจข้อมูลก่อนรัน** "ใช่" = มี SQL หรือโค้ดตรวจข้อมูลที่ตรงกับความเสี่ยงที่แจ้งอย่างน้อย 1 อัน (เช่น หาค่าซ้ำ นับ NULL) "ไม่" = มีแต่คำแนะนำว่าให้ตรวจ โดยไม่มี query
6. **มีแผนถอยกลับ** "ใช่" = ระบุว่าถอยได้หรือไม่ และระบุว่าข้อมูลส่วนไหนถอยแล้วไม่กลับ (หรือบอกว่าทางเดียวคือกู้จากสำรอง) "บางส่วน" = พูดถึงเฉพาะบางเรื่องโดยไม่มีแผนครบ "ไม่" = ไม่มี
7. **บอกสิ่งที่ไฟล์บอกไม่ได้** "ใช่" = มีข้อความหรือหัวข้อระบุชัดว่าการตรวจนี้ยืนยันอะไรไม่ได้ (เช่น ขนาดตาราง โค้ดที่ยังใช้คอลัมน์ เวอร์ชัน DB) "ไม่" = ไม่มี (การสั่งให้ไปตรวจแทรกในข้อแนะนำอย่างเดียวไม่นับ)
8. **ไม่สรุปว่า "ปลอดภัย" ลอย ๆ** "ใช่" = ไม่มีข้อสรุปว่าปลอดภัยหรือรันได้เลยโดยไม่ระบุสิ่งที่ยืนยันไม่ได้ "ไม่" = มีข้อสรุปแบบนั้น

## ใช้ชุดทดสอบนี้กับ Skill เวอร์ชันถัดไป

1. ส่งไฟล์ใน `fixtures/` ให้ AI ทีละเคส ด้วย prompt เดียวกันทั้งสองฝั่ง (ฝั่ง Skill ใส่ `/migration-safety-review` นำหน้า)
2. แยกเซสชันแต่ละรอบ ห้ามให้ AI เห็นไฟล์นี้
3. ตรวจเทียบตารางด้านบนด้วยเกณฑ์ 8 ข้อ แล้วบันทึกคำตอบดิบไว้ใน `evaluation/`
