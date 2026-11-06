## สรุป
- ไฟล์: [case4_irreversible_runpython.py](fixtures/case4_irreversible_runpython.py) | เครื่องมือ/DB: Django migration (`analytics.0031_event_source` เป็น dependency), PostgreSQL ตามที่ระบุในไฟล์ ตาราง `events` ประมาณ 30 ล้านแถว ไม่ทราบเวอร์ชัน DB ไม่ทราบวิธี deploy
- ระดับรวม: **HIGH**
- คำแนะนำ: **อย่าเพิ่งรัน** จนกว่าจะแก้ข้อ 1 และ 2 (แยก data migration ออก, ทำเป็น batch, ใส่ `reverse_code`, เปลี่ยน index เป็น `AddIndexConcurrently` และตั้ง `atomic = False`)
- ตรวจแล้ว 2 operation: HIGH x1, MEDIUM x1, LOW x0, OK x0
- ไม่พบ CLAUDE.md / AGENTS.md ในโปรเจกต์ จึงไม่มีข้อห้ามเรื่องการรัน migration เพิ่มเติม ฉันตรวจโดยอ่านไฟล์อย่างเดียว ไม่ได้รันอะไร

## ตารางความเสี่ยง
| # | Operation | หมวด | ระดับ | ปัญหา | วิธีลดความเสี่ยง |
|---|-----------|------|-------|-------|------------------|
| 1 | `RunPython(normalize_event_types)` บรรทัด 20 (`Event.objects.update(event_type=Lower("event_type"))` บรรทัด 10) บน `events.event_type` | IRREVERSIBLE, LOCK/DOWNTIME, DATA LOSS, DATA INTEGRITY | **HIGH** | (ก) ไม่มี `reverse_code` จึงถอยกลับ migration ไม่ได้ (Django จะ error ตอน unapply) (ข) ตัวพิมพ์เล็กใหญ่เดิมของ `event_type` ถูกเขียนทับและกู้คืนไม่ได้ เพราะ `Lower` ไม่มีฟังก์ชันผกผัน (ค) `UPDATE` ทุกแถวใน transaction เดียว 30 ล้านแถว โดยทั่วไปจะถือ row lock นาน, WAL และตารางบวม (bloat) มาก และถ้าล้มกลางทางต้อง rollback ทั้งหมด (ง) `UPDATE` เขียนแถวใหม่แม้ค่าเดิมเป็นตัวพิมพ์เล็กอยู่แล้ว (จ) ถ้ามีค่าที่ต่างกันแค่ตัวพิมพ์ (`Click`/`click`) จะถูกรวมเป็นค่าเดียว ถ้าโค้ดหรือ report ใช้ค่าเดิมจะเพี้ยน | สำรองคอลัมน์ก่อน (เช่น คัดลอกเป็น `event_type_old` หรือ snapshot ตาราง) ใส่ `reverse_code` (อย่างน้อย `migrations.RunPython.noop` เมื่อยอมรับว่าไม่กลับค่าเดิม) กรองเฉพาะแถวที่ต้องแก้ `.exclude(event_type=Lower("event_type"))` แบ่ง batch ตามช่วง `id` พร้อม commit ทีละก้อน (`atomic = False`) หรือแยกเป็นสคริปต์/ไฟล์ data migration ต่างหาก |
| 2 | `AddIndex` `events_occurred_at_idx` บน `events.occurred_at` | LOCK/DOWNTIME, DEPLOY ORDER (รวม schema กับ data migration) | **MEDIUM** (ต้องรู้ขนาดตารางจริงและช่วงเวลา deploy) | โดยทั่วไป `CREATE INDEX` แบบปกติบน PostgreSQL บล็อกการเขียน (INSERT/UPDATE/DELETE) ตลอดการสร้าง บนตาราง 30 ล้านแถวอาจนานหลายนาที ซึ่งกระทบ ingestion ถ้ามีการเขียนต่อเนื่อง นอกจากนี้ index อยู่ใน transaction เดียวกับ RunPython ทำให้ lock จาก UPDATE ยืดไปถึงตอนสร้าง index | ใช้ `django.contrib.postgres.operations.AddIndexConcurrently` และตั้ง `atomic = False` ใน `Migration` หรือแยก index เป็น migration ของตัวเอง ตั้ง `lock_timeout` ทำช่วงโหลดต่ำ ตรวจเอกสาร PostgreSQL ของเวอร์ชันจริง |

## ตรวจข้อมูลก่อนรัน
```sql
-- จำนวนแถวที่ต้องถูกแก้จริง (ถ้าน้อยมาก อาจไม่ต้อง update ทั้งตาราง)
SELECT COUNT(*) FROM analytics_event WHERE event_type <> LOWER(event_type);

-- ค่าที่จะถูกรวมกันหลัง lower (ผลที่ยอมรับได้ = ทีมยืนยันแล้วว่ารวมกันได้)
SELECT LOWER(event_type) AS normalized, COUNT(DISTINCT event_type) AS variants
FROM analytics_event
GROUP BY 1 HAVING COUNT(DISTINCT event_type) > 1;

-- ขนาดตารางและ index เดิม
SELECT pg_size_pretty(pg_total_relation_size('analytics_event'));

-- ธุรกรรมยาวหรือ lock ที่ค้างอยู่ก่อนรัน
SELECT pid, state, now() - xact_start AS age, query FROM pg_stat_activity WHERE xact_start IS NOT NULL ORDER BY age DESC;
```
(ชื่อตาราง `analytics_event` เป็นการเดาตามค่า default ของ Django ตรวจ `db_table` จริงอีกครั้ง)

ควรค้นโค้ดด้วยว่ามี unique constraint หรือ index บน `event_type` ที่ lower แล้วจะชนกันหรือไม่

## เช็กลิสต์ก่อนรัน
- [ ] สำรองข้อมูล/snapshot (รวมค่า `event_type` เดิม) และทดสอบว่ากู้คืนได้จริง
- [ ] ทดสอบบน staging ที่มีข้อมูลขนาดใกล้ 30 ล้านแถว วัดเวลา, ขนาด WAL, bloat
- [ ] แก้ migration: ใส่ `reverse_code`, ทำ batch, เปลี่ยนเป็น `AddIndexConcurrently` + `atomic = False`
- [ ] ยืนยันว่าโค้ด/ dashboard ที่อ่าน `event_type` รองรับค่าตัวพิมพ์เล็กทั้งหมด และโค้ดที่เขียนค่าใหม่ normalize เป็นตัวพิมพ์เล็กก่อน (ไม่งั้นข้อมูลใหม่จะกลับมาปนกันอีก)
- [ ] ลำดับ deploy: deploy โค้ดที่ normalize ค่าตอนเขียน → รัน data migration → สร้าง index
- [ ] ช่วงเวลาโหลดต่ำ มีคนเฝ้า ตั้ง `lock_timeout`/`statement_timeout` และมีแผนยกเลิกถ้าช้าเกินไป
- [ ] ตรวจพื้นที่ดิสก์ว่าพอสำหรับ WAL และ index ใหม่

## แผนถอยกลับ
- **RunPython:** ปัจจุบันถอยไม่ได้ ถ้ารันแล้วค่าตัวพิมพ์เดิมหายถาวร **ทางเดียวคือกู้จากสำรองข้อมูล** (หรือจากคอลัมน์/ตารางสำรองที่ทำไว้ก่อนรัน) แม้ใส่ `noop` เป็น reverse ก็แค่ให้ Django unapply ได้ แต่ไม่คืนค่าเดิม
- **AddIndex:** ถอยได้ด้วย unapply (DROP INDEX) ไม่สูญเสียข้อมูล แต่ถ้า migration ล้มระหว่าง `CONCURRENTLY` จะเหลือ index สถานะ invalid ต้อง drop เองก่อนรันใหม่
- ถ้า migration ล้มกลางทางใน transaction เดียว PostgreSQL จะ rollback ทั้งก้อน (ใช้เวลา rollback นานได้เช่นกัน)

## สิ่งที่ไฟล์นี้บอกไม่ได้
- เวอร์ชัน PostgreSQL และการตั้งค่า (พฤติกรรม lock, autovacuum) รวมถึงอัตรา write บน `events` ตอน deploy
- ชื่อตารางจริง (`db_table`) และมี index/constraint/trigger อื่นบน `event_type` หรือไม่ (รวมถึง partition, replication ที่จะรับ WAL ปริมาณมาก)
- สัดส่วนแถวที่ `event_type` ไม่ใช่ตัวพิมพ์เล็กอยู่แล้ว และมีค่าที่จะถูกรวมกันหรือไม่
- โค้ดส่วนอื่น (API, dashboard, ETL) ที่เปรียบเทียบ `event_type` แบบ case-sensitive หรือยังเขียนค่าตัวพิมพ์ใหญ่
- วิธี deploy (ปิดระบบ/rolling) และ dependency ฝั่งไฟล์ migration อื่นที่อาจมี leaf node ซ้อนกันต่อจาก `0031_event_source` (ฉันไม่ได้ตรวจโฟลเดอร์ migration ทั้งหมด)
