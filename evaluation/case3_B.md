## สรุป
- ไฟล์: fixtures/case3_postgres_ddl.sql | เครื่องมือ/DB (สมมติฐาน): raw SQL บน PostgreSQL 15 (ตามคอมเมนต์ในไฟล์), orders ประมาณ 50 ล้านแถว, ไม่ทราบขนาด users, ไม่ทราบว่า deploy แบบ rolling หรือปิดระบบ จึงสมมติว่าโค้ดเก่ากับโค้ดใหม่รันคาบเกี่ยวกันช่วงหนึ่ง, ไม่ทราบว่าเครื่องมือรันทั้งไฟล์ใน transaction เดียวหรือไม่
- ระดับรวม: HIGH
- คำแนะนำ: อย่าเพิ่งรัน จนกว่าจะแก้ข้อ 1 (`orders.status` เป็น NOT NULL ไม่มี default) และข้อ 3 (`DROP COLUMN users.phone` ควรแยกไปรันหลัง deploy โค้ดเสร็จและสำรองข้อมูลแล้ว) ส่วนข้อ 2 และข้อ 4 ควรปรับเป็นแบบ online และรัน query ตรวจข้อมูลก่อน
- ตรวจแล้ว 4 operation: HIGH 2, MEDIUM 2, LOW 0, OK 0
- หมายเหตุ: ตรวจครบทุกคำสั่งในไฟล์ แต่ไม่ได้แปลว่าปลอดภัย ยังมีสิ่งที่ไฟล์ยืนยันไม่ได้ (ดูหัวข้อท้ายสุด) ผลนี้เป็นข้อมูลส่งต่อให้ผู้ดูแลที่รันเอง ผมไม่ได้รัน migration หรือคำสั่งใด ๆ กับ DB

## ตารางความเสี่ยง
| # | Operation | หมวด | ระดับ | ปัญหา | วิธีลดความเสี่ยง |
|---|-----------|------|-------|-------|------------------|
| 1 | `ALTER TABLE orders ADD COLUMN status VARCHAR(20) NOT NULL` | CONSTRAINT ON EXISTING DATA, DEPLOY ORDER, LOCK/DOWNTIME | HIGH | (1) เพิ่มคอลัมน์ NOT NULL โดยไม่มี DEFAULT บนตารางที่มีข้อมูลอยู่แล้ว (ประมาณ 50 ล้านแถว) โดยทั่วไป PostgreSQL จะ error เพราะแถวเดิมไม่มีค่า คำสั่งนี้จึงรันไม่ผ่านแน่ (2) ต่อให้แก้ให้ผ่าน โค้ดเก่าที่ไม่รู้จัก `status` จะ INSERT ลง orders ไม่ผ่านระหว่าง deploy (3) ADD COLUMN โดยทั่วไปขอ lock แรงบน orders แม้ช่วงสั้น ถ้ามี transaction ยาวค้างอยู่ จะต่อคิวและบล็อก query อื่นบน orders ตามไปด้วย | เลือกตามความหมายของข้อมูล A) ถ้ามีค่าเริ่มต้นที่ถูกต้องสำหรับทุกแถวเดิม ใช้ `ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT '<ค่า>'` โดยทั่วไป PostgreSQL 11 ขึ้นไปเติม default ค่าคงที่โดยไม่เขียนตารางใหม่ แต่ทุกแถวเดิมจะได้ค่าเดียวกัน ต้องยืนยันว่าตรงความตั้งใจ B) ถ้าแถวเดิมต้องการค่าจริง ให้ทำแบบ expand/contract (ดูหัวข้อเช็กลิสต์) ทุกกรณีตั้ง `lock_timeout` ก่อนรัน |
| 2 | `CREATE INDEX idx_orders_created_at ON orders (created_at)` | LOCK/DOWNTIME | MEDIUM | CREATE INDEX ปกติโดยทั่วไปบล็อกการเขียน (INSERT/UPDATE/DELETE) บน orders ตลอดการสร้าง ที่ประมาณ 50 ล้านแถวอาจนานหลายนาที (ต้องวัดบน staging) เท่ากับหยุดเขียนตารางหลักช่วงนั้น ระดับ MEDIUM เพราะขึ้นกับเวลาสร้างจริงและโหลดขณะรัน แต่ขนาดที่แจ้งมาใหญ่พอที่ควรแก้ก่อนรัน | ใช้ `CREATE INDEX CONCURRENTLY idx_orders_created_at ON orders (created_at);` คำสั่งนี้รันใน transaction block ไม่ได้ ต้องแยกไฟล์หรือปิด transaction ของไฟล์นั้นตามเครื่องมือที่ใช้ ถ้าล้มกลางทางจะเหลือ index สถานะ INVALID ต้อง `DROP INDEX CONCURRENTLY` แล้วสร้างใหม่ ทำช่วงโหลดต่ำและเช็กพื้นที่ดิสก์ |
| 3 | `ALTER TABLE users DROP COLUMN phone` | DATA LOSS, IRREVERSIBLE, DEPLOY ORDER | HIGH | (1) ข้อมูลเบอร์โทรทั้งหมดหาย ถอยได้แค่โครงสร้าง ข้อมูลไม่กลับมา ทางเดียวคือกู้จากสำรองข้อมูล (2) ไฟล์ระบุว่า apply พร้อม deploy แอป ถ้า migration เสร็จก่อนโค้ดใหม่ขึ้นครบ โค้ดเก่าที่ยังอ่านหรือเขียน `users.phone` จะ error และหลังลบแล้ว rollback แอปกลับเวอร์ชันเก่าไม่ได้ เพราะโค้ดเก่าต้องใช้ phone (3) ถ้ามี view/function ที่อ้างถึง phone คำสั่งอาจล้ม หรือถ้าใช้ CASCADE จะลบของที่พึ่งพาไปด้วย (โดยทั่วไป DROP COLUMN ใน PostgreSQL ไม่เขียนตารางใหม่ แต่ขอ lock แรงช่วงสั้น) | แยกเป็น migration ขั้น contract รันหลังโค้ดใหม่ deploy ครบ ไม่มีโค้ดเก่าเหลือ และเฝ้าดูระยะหนึ่ง ก่อนลบให้สำรองคอลัมน์ (เช่นตารางสำรอง id + phone) หรือยืนยันว่าข้อมูลถูกย้ายแล้ว/ไม่ต้องเก็บ (ตรวจนโยบายข้อมูลส่วนบุคคลด้วย) ตรวจ dependency (view, index, trigger, function) และ consumer อื่น (report, BI, ETL) ตั้ง `lock_timeout` และไม่ใช้ CASCADE |
| 4 | `ALTER TABLE users ADD CONSTRAINT uq_users_email UNIQUE (email)` | CONSTRAINT ON EXISTING DATA, LOCK/DOWNTIME | MEDIUM (เป็น HIGH ถ้า query ตรวจพบอีเมลซ้ำ) | (1) ล้มถ้า users มี email ซ้ำ ไฟล์ยืนยันไม่ได้ว่าซ้ำหรือไม่ (2) โดยทั่วไปต้องสร้าง unique index ซึ่งบล็อกการเขียนบน users ระหว่างสร้าง ไม่ทราบขนาด users จึงต้องรู้ขนาดตารางก่อนประเมิน (3) DB มอง `A@x.com` กับ `a@x.com` หรือค่าที่มีช่องว่างท้ายเป็นคนละค่า จึงอาจซ้ำในมุมธุรกิจแต่ผ่าน constraint และโดยทั่วไป NULL ซ้ำได้ (4) โค้ดสมัครสมาชิก/แก้อีเมลต้องรับมือกับ unique violation | รัน query ตรวจค่าซ้ำและแก้ข้อมูลก่อน แล้วใช้ `CREATE UNIQUE INDEX CONCURRENTLY uq_users_email ON users (email);` ตามด้วย `ALTER TABLE users ADD CONSTRAINT uq_users_email UNIQUE USING INDEX uq_users_email;` (ขั้นหลังขอ lock แรงช่วงสั้น) ถ้าธุรกิจต้องการไม่สนตัวพิมพ์เล็กใหญ่ ให้พิจารณา unique index บน `lower(email)` และให้แอปค้นหาแบบเดียวกัน |

## ตรวจข้อมูลก่อนรัน
ข้อ 1 ไม่ต้องมี query ตรวจ เพราะ orders มีข้อมูลอยู่แล้ว คำสั่งจะล้มแน่ถ้าไม่มี default ส่วน query ด้านล่างเป็นแบบอ่านอย่างเดียว ให้ผู้ดูแลรันเอง (ควรรันบน replica หรือช่วงโหลดต่ำ) และปรับชื่อ schema ตามจริง

```sql
-- ข้อ 1, 2, 4: ขนาดจริงของตาราง (ต้องรู้ก่อนประเมิน lock และเวลาสร้าง index)
SELECT relname, reltuples::bigint AS est_rows, pg_size_pretty(pg_total_relation_size(oid)) AS total_size
FROM pg_class WHERE relkind = 'r' AND relname IN ('orders', 'users');

-- ข้อ 4: email ซ้ำแบบตรงตัว (ผลที่ยอมรับได้ = 0 แถว)
SELECT email, COUNT(*) FROM users GROUP BY email HAVING COUNT(*) > 1;

-- ข้อ 4: ซ้ำในมุมธุรกิจ ตัวพิมพ์เล็กใหญ่/ช่องว่างท้าย (ผลที่ยอมรับได้ = 0 แถว ถ้ามี ต้องตัดสินใจก่อนว่านับเป็นซ้ำหรือไม่)
SELECT lower(btrim(email)) AS e, COUNT(*) FROM users GROUP BY 1 HAVING COUNT(*) > 1;

-- ข้อ 4: มี unique index บน email อยู่แล้วหรือไม่ (ถ้ามี constraint ใหม่อาจซ้ำซ้อน)
SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'users' AND indexdef ILIKE '%email%';

-- ข้อ 3: ข้อมูลที่จะหาย (ถ้า > 0 ต้องสำรองหรือยืนยันว่าไม่ต้องใช้ก่อนลบ)
SELECT COUNT(*) FROM users WHERE phone IS NOT NULL;

-- ข้อ 3: view และ index ที่พึ่ง phone (ผลที่ยอมรับได้ = ไม่มี หรือรู้แล้วว่าจะจัดการอย่างไร)
SELECT view_schema, view_name FROM information_schema.view_column_usage
WHERE table_name = 'users' AND column_name = 'phone';
SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'users' AND indexdef ILIKE '%phone%';

-- ข้อ 1, 3, 4: transaction ยาวที่ทำให้ ALTER ต่อคิวและบล็อกคนอื่น (ผลที่ยอมรับได้ = ไม่มี transaction ที่เปิดค้างนาน)
SELECT pid, now() - xact_start AS age, state, left(query, 80) AS query
FROM pg_stat_activity WHERE xact_start IS NOT NULL ORDER BY xact_start LIMIT 10;

-- หลังรันแบบ CONCURRENTLY: index ที่สถานะ INVALID (ผลที่ยอมรับได้ = 0 แถว)
SELECT indexrelid::regclass FROM pg_index WHERE NOT indisvalid;
```

## เช็กลิสต์ก่อนรัน
- [ ] สำรองข้อมูล/snapshot (อย่างน้อย `users.phone` ก่อนข้อ 3) และยืนยันว่ากู้คืนได้จริง
- [ ] ทดสอบบน staging ที่มีข้อมูลขนาดใกล้เคียงจริง (orders ประมาณ 50 ล้านแถว) จับเวลาสร้าง index และ ADD COLUMN ดู replication lag
- [ ] ลำดับ deploy โค้ดกับ migration ตามแผนแบ่งขั้นด้านล่าง ไม่รันทั้งไฟล์พร้อม deploy ในครั้งเดียว
- [ ] ช่วงเวลาที่ล็อกได้ / คนที่เฝ้า ตั้ง `lock_timeout` (เช่น 3-5 วินาที) และ `statement_timeout` ให้เหมาะสม มีคนเฝ้า `pg_stat_activity`
- [ ] ยืนยันว่าเครื่องมือรัน migration หยุดทันทีเมื่อ error (เช่น psql ต้องใช้ `-v ON_ERROR_STOP=1` เพราะโดยทั่วไปค่าเริ่มต้นจะรันคำสั่งถัดไปต่อ ทำให้ `DROP COLUMN` ถูกรันทั้งที่ข้อ 1 ล้ม) และแยกไฟล์ที่ใช้ CONCURRENTLY ออกจากไฟล์ที่ต้องอยู่ใน transaction
- [ ] ยืนยันว่าโค้ดใหม่ไม่อ่าน `users.phone` และไม่มีบริการอื่นอ่านอยู่
- [ ] ตรวจเอกสาร PostgreSQL 15 เรื่อง lock ของแต่ละคำสั่ง (ข้อมูลใน review นี้เขียนแบบ "โดยทั่วไป")

แนวทางแบ่งขั้น (expand/contract) ที่เสนอ:
1. Migration A (expand, รันก่อนหรือพร้อม deploy โค้ดใหม่): `ALTER TABLE orders ADD COLUMN status VARCHAR(20);` (nullable) หรือ `NOT NULL DEFAULT '<ค่า>'` ถ้ายืนยัน default ได้ (ตั้ง `lock_timeout` ก่อน)
2. Migration B (ไฟล์ที่ไม่อยู่ใน transaction): `CREATE INDEX CONCURRENTLY idx_orders_created_at ...;` และ `CREATE UNIQUE INDEX CONCURRENTLY uq_users_email ...;` (หลังแก้อีเมลซ้ำแล้ว) ตามด้วย `ADD CONSTRAINT ... UNIQUE USING INDEX ...`
3. Deploy โค้ดใหม่ให้ครบ (ทุก INSERT เขียน `status`, เลิกใช้ `phone`) จนไม่มีโค้ดเก่าเหลือ
4. Backfill `status` ของแถวเดิมเป็น batch (เช่นครั้งละหมื่นถึงหลายหมื่นแถว พักระหว่าง batch) ห้าม UPDATE 50 ล้านแถวใน transaction เดียว
5. บังคับ NOT NULL แบบ online:
   ```sql
   ALTER TABLE orders ADD CONSTRAINT orders_status_not_null CHECK (status IS NOT NULL) NOT VALID;
   ALTER TABLE orders VALIDATE CONSTRAINT orders_status_not_null;
   ALTER TABLE orders ALTER COLUMN status SET NOT NULL;  -- โดยทั่วไป PostgreSQL 12 ขึ้นไปใช้ CHECK ที่ validate แล้วข้ามการสแกนทั้งตาราง ตรวจเอกสาร PG 15
   ALTER TABLE orders DROP CONSTRAINT orders_status_not_null;
   ```
6. Migration C (contract, release หรือ migration ถัดไป หลังเฝ้าดูระยะหนึ่ง): สำรอง `phone` แล้ว `ALTER TABLE users DROP COLUMN phone;`

## แผนถอยกลับ
- ข้อ 1 (`orders.status`): ถอยได้ด้วย `ALTER TABLE orders DROP COLUMN status;` แต่ค่า status ที่แอปเขียนหลัง deploy จะหายไปพร้อมคอลัมน์
- ข้อ 2 (`idx_orders_created_at`): ถอยได้ด้วย `DROP INDEX CONCURRENTLY idx_orders_created_at;` ไม่กระทบข้อมูล
- ข้อ 3 (`users.phone`): ถอยจริงไม่ได้ ย้อนโครงสร้างได้ด้วย `ALTER TABLE users ADD COLUMN phone <ชนิดเดิม>;` (ชนิดเดิมไม่อยู่ในไฟล์นี้ ต้องดูจาก schema จริง) แต่ข้อมูลเบอร์ที่หายไม่กลับมา ทางเดียวคือกู้จากสำรองข้อมูล และหลังลบแล้ว rollback แอปไปเวอร์ชันเก่าไม่ได้เพราะโค้ดเก่าต้องใช้ phone
- ข้อ 4 (`uq_users_email`): ถอยได้ด้วย `ALTER TABLE users DROP CONSTRAINT uq_users_email;` ไม่กระทบข้อมูล
- ถ้าเครื่องมือห่อทั้งไฟล์ใน transaction เดียวแล้วล้มกลางทาง โดยทั่วไป PostgreSQL ย้อน DDL ทั้งไฟล์ให้ แต่ถ้ารันแบบไม่ใช่ transaction เดียว หรือแยกไฟล์ที่ใช้ CONCURRENTLY คำสั่งที่รันสำเร็จแล้วจะค้างอยู่ ต้องไล่ถอยทีละข้อตามด้านบน
- ข้อมูลที่ถอยแล้วไม่กลับมา: `users.phone` ทั้งหมด (ข้อ 3) ส่วนข้ออื่นถอยได้ แต่คำสั่งถอยก็ขอ lock จึงควรตั้ง `lock_timeout` เช่นกัน

## สิ่งที่ไฟล์นี้บอกไม่ได้
- ขนาดและจำนวนแถวจริงของ `users` และ `orders` (ขนาด orders ประมาณ 50 ล้านแถวมาจากคอมเมนต์ในไฟล์ ไม่ได้ยืนยัน) รวมถึงอัตราการเขียนและโหลดในช่วงที่จะรัน
- มี email ซ้ำ (รวมถึงต่างตัวพิมพ์เล็กใหญ่หรือมีช่องว่างท้าย) ใน `users` หรือไม่ และมี unique index บน email อยู่แล้วหรือไม่
- ค่า `status` ที่ถูกต้องสำหรับแถวเดิมของ orders และโค้ดเก่า/ใหม่เขียน `status` ตอน INSERT หรือไม่ (คอมเมนต์ในไฟล์พูดถึงแต่ `users.phone`)
- ข้อมูลใน `users.phone` มีอยู่เท่าไร ต้องเก็บตามกฎหมาย/นโยบาย/ฝ่ายอื่นหรือไม่ ถูกย้ายไปที่อื่นแล้วหรือยัง และชนิดเดิมของคอลัมน์
- โค้ดหรือบริการอื่นที่ยังอ่าน `users.phone` (report, BI, ETL, cron, service อื่น, replica/logical replication) และ view/function/trigger ที่พึ่ง phone
- วิธี deploy จริง (rolling หรือปิดระบบ) และลำดับระหว่าง migration กับ deploy แอป
- เครื่องมือที่ใช้รันไฟล์ (Flyway, psql หรืออื่น ๆ) และว่าห่อทั้งไฟล์ใน transaction เดียวหรือไม่ ซึ่งกระทบทั้ง `CONCURRENTLY` และพฤติกรรมเมื่อล้มกลางไฟล์
- เวอร์ชันย่อยและการตั้งค่าจริงของ PostgreSQL 15 (`lock_timeout`, `statement_timeout`, replication lag, พื้นที่ดิสก์ว่าง) และเอกสาร lock ของเวอร์ชันนั้น
- โครงสร้างปัจจุบันของตาราง (index, FK, trigger, view ที่เกี่ยวข้อง) เพราะไฟล์นี้มีแต่ส่วนที่เปลี่ยน
