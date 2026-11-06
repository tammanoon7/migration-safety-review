**สรุป: ยังไม่ควรปล่อย migration นี้ เพราะมี 1 จุดที่รันไม่ผ่านแน่ และอีก 3 จุดเสี่ยงต่อ production**

**1. `ADD COLUMN status VARCHAR(20) NOT NULL` (ร้ายแรง)**
- คำสั่งนี้ไม่มี DEFAULT ตารางมีข้อมูลอยู่แล้ว 50 ล้านแถว PostgreSQL จึงจะ error ว่า column contains null values และ release จะล้มทั้งชุด
- ใน PG 15 การเพิ่มคอลัมน์ที่มี DEFAULT เป็นค่าคงที่ทำได้เร็วเพราะแก้แค่ metadata และไม่ rewrite ตาราง
- ต้องให้ทีมธุรกิจตัดสินใจว่าค่า default ของ status ควรเป็นอะไร ตัวอย่างนี้ใช้ `'pending'` เป็นค่าสมมติ

```sql
ALTER TABLE orders ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'pending';
```

- ถ้าไม่อยากมี default ถาวร ให้เพิ่มเป็น nullable ก่อน แล้ว backfill เป็น batch จากนั้นเพิ่ม `CHECK (status IS NOT NULL) NOT VALID` แล้ว `VALIDATE CONSTRAINT` สุดท้ายค่อย `SET NOT NULL`

**2. `CREATE INDEX idx_orders_created_at` (เสี่ยงสูง)**
- คำสั่งนี้ block การ INSERT, UPDATE และ DELETE บน `orders` ตลอดเวลาที่สร้าง index บน 50 ล้านแถว ซึ่งอาจนานหลายนาที
- ให้ใช้ `CONCURRENTLY` และเพิ่ม `IF NOT EXISTS`

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_created_at ON orders (created_at);
```

- `CONCURRENTLY` รันใน transaction block ไม่ได้ ต้องตั้ง migration tool ให้รันคำสั่งนี้นอก transaction
- ถ้าสร้างไม่สำเร็จ จะเหลือ index สถานะ INVALID ต้อง `DROP INDEX CONCURRENTLY` แล้วสร้างใหม่

**3. `DROP COLUMN phone` (เสี่ยงสูง ย้อนกลับไม่ได้)**
- migration นี้ถูก apply ใน release เดียวกับ app deploy ระหว่าง rolling deploy instance เก่ายังอ่านหรือเขียน `users.phone` อยู่ จึงจะ error
- ถ้า rollback app หลัง drop แล้ว ข้อมูลเบอร์โทรจะหายถาวร
- ควรใช้ expand/contract คือ deploy app ที่เลิกใช้ `phone` ก่อน ยืนยันว่าเสถียร แล้วค่อย drop ใน release ถัดไป
- ก่อน drop ควร backup หรือ archive ข้อมูลเบอร์โทร และตรวจว่าไม่มี view, function หรือ report ที่อ้างถึงคอลัมน์นี้
- การ drop ทำเร็วเพราะแก้แค่ metadata แต่ต้องใช้ ACCESS EXCLUSIVE lock

**4. `ADD CONSTRAINT uq_users_email UNIQUE (email)` (เสี่ยงปานกลางถึงสูง)**
- คำสั่งนี้สร้าง unique index โดยถือ lock ที่ block งานบน `users` ตลอดการ build
- ถ้ามี email ซ้ำอยู่แล้ว คำสั่งจะล้ม ต้องตรวจก่อนว่ามีข้อมูลซ้ำหรือไม่
- ต้องตัดสินใจเรื่องตัวพิมพ์เล็กและใหญ่ด้วย เช่น ใช้ `lower(email)` หรือ `citext`
- แนวทางที่ปลอดภัยกว่า:

```sql
-- ตรวจข้อมูลซ้ำก่อน
SELECT email, count(*) FROM users GROUP BY email HAVING count(*) > 1;

CREATE UNIQUE INDEX CONCURRENTLY uq_users_email ON users (email);
ALTER TABLE users ADD CONSTRAINT uq_users_email UNIQUE USING INDEX uq_users_email;
```

**ข้อเสนอแนะทั่วไป**
- ตั้ง `SET lock_timeout = '5s';` ก่อนคำสั่ง ALTER ที่ต้องใช้ lock เพื่อไม่ให้คิวรอ lock ค้างจนบล็อกทั้งระบบ และเตรียม retry
- ควรมี down/rollback script หรือแผน rollback ที่ชัดเจน ซึ่งขณะนี้ยังไม่มี
- แยก migration เป็นหลายขั้น (เพิ่มคอลัมน์ สร้าง index และ constraint แล้วค่อย drop ใน release ถัดไป) และทดสอบกับข้อมูลขนาดใกล้เคียง production ก่อน
