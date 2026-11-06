---
name: migration-safety-review
description: Review database migration files for risk before a human runs them - data loss, NOT NULL or unique constraints on existing rows, table locking, irreversible steps, and code/schema deploy-order breakage. Produces a per-operation risk table, data-check queries, a pre-run checklist and a rollback plan. Use when the user asks to check, review or approve a migration (ตรวจ migration, ก่อนรัน migrate, migration นี้ปลอดภัยไหม, review ไฟล์ migration). Works with Django, Alembic, Flyway, Liquibase, Prisma, Rails, Knex or raw SQL.
---

# Migration Safety Review

ตรวจไฟล์ migration ก่อนมีคนรันจริง **อ่านและวิเคราะห์เท่านั้น** ห้ามรันคำสั่ง migrate / upgrade / apply ใด ๆ

## Input
- ไฟล์ migration หนึ่งไฟล์หรือหลายไฟล์ (หรือเนื้อหา SQL ที่วางมา)
- (ถ้ามี) ชนิดและเวอร์ชัน DB, ขนาดตารางที่เกี่ยวข้อง, วิธี deploy (ปิดระบบ / rolling)
- ถ้าไม่ระบุ ให้ระบุสมมติฐานเองในผลลัพธ์ อย่าหยุดถาม ยกเว้นความเสี่ยงข้อสำคัญเปลี่ยนไปตามคำตอบจริง ๆ

## Workflow
1. **ระบุบริบท**: เครื่องมือ migration, ชนิด DB (พฤติกรรมล็อกต่างกัน), ลำดับ dependency ของไฟล์
2. **แตกทีละ operation**: ไล่ทุกคำสั่งในไฟล์ ห้ามอ่านผ่าน ๆ แล้วสรุปรวม แต่ละ operation หนึ่งแถวในตาราง
   (ตารางใหม่ที่ว่างถือว่า OK ไม่ต้องขยายความ)
3. **จัดหมวดความเสี่ยง** ตาม `references/risk-checklist.md` (อ่านไฟล์นี้ก่อนให้ระดับทุกครั้ง):
   DATA LOSS, CONSTRAINT ON EXISTING DATA, LOCK/DOWNTIME, IRREVERSIBLE, DEPLOY ORDER, DATA INTEGRITY
   operation เดียวอาจเข้าหลายหมวด ให้ระบุทุกหมวดที่เกี่ยวข้อง
4. **ให้ระดับ** HIGH / MEDIUM / LOW / OK (ระดับของ operation = ระดับสูงสุดของหมวดที่พบ)
   - HIGH: ข้อมูลหาย, รันไม่ผ่านแน่เมื่อมีข้อมูล, หรือถอยกลับไม่ได้
   - MEDIUM: ขึ้นกับขนาดข้อมูลหรือลำดับ deploy
   - LOW: ผลกระทบเล็กหรือเป็นข้อสังเกต
   - ความเสี่ยงที่ขึ้นกับขนาดตารางแต่ไม่ทราบขนาด ให้ถือเป็น MEDIUM และเขียนว่าต้องรู้ขนาดตาราง
5. **เขียนมาตรการ**: query ตรวจข้อมูลก่อนรัน, เช็กลิสต์ก่อนรัน, แผนถอยกลับ,
   แนวทางแบ่งขั้น (เช่น expand/contract) ถ้าควรแยก migration
6. **บอกสิ่งที่ไฟล์บอกไม่ได้**: ขนาดและข้อมูลจริงในตาราง, โค้ดที่ยังอ่านคอลัมน์ที่จะลบ, เวอร์ชัน DB

## Rules
- ห้ามรัน migrate / makemigrations / upgrade / flyway / prisma migrate หรือคำสั่งที่แก้ DB ใด ๆ
- ห้ามสรุปว่า "ปลอดภัย" ลอย ๆ ต้องบอกว่าตรวจครบกี่ operation และมีอะไรที่ไฟล์ยืนยันไม่ได้
- ห้ามแจ้งตารางใหม่ที่เพิ่งสร้างว่าเสี่ยงสูงถ้าไม่มีเหตุผลเฉพาะ (หลีกเลี่ยง false positive)
- ทุกข้อที่แจ้งต้องชี้ operation ที่เกิดเรื่อง (ชื่อ operation + ตารางและคอลัมน์ หรือเลขบรรทัด)
- ข้อเท็จจริงเรื่อง lock ขึ้นกับชนิดและเวอร์ชัน DB ให้เขียนว่า "โดยทั่วไป" และแนะนำให้ตรวจเอกสารของเวอร์ชันจริง
- ถ้าโปรเจกต์ห้ามให้ AI รัน migration (ดู CLAUDE.md / AGENTS.md) ให้เขียนผลเป็นข้อมูลส่งต่อให้ผู้ดูแลที่รันเอง
- ไม่แก้ไฟล์ migration เอง ให้เสนอวิธีแก้เป็นข้อความหรือตัวอย่างโค้ด

## Output
ใช้ template นี้ (ตัดหัวข้อที่ไม่เกี่ยวข้องได้ แต่ห้ามตัด "สิ่งที่ไฟล์นี้บอกไม่ได้"):

```markdown
## สรุป
- ไฟล์: ... | เครื่องมือ/DB (สมมติฐาน): ...
- ระดับรวม: HIGH / MEDIUM / LOW / OK
- คำแนะนำ: อย่าเพิ่งรัน จนกว่าจะทำข้อ ... / รันได้หลังทำเช็กลิสต์ด้านล่าง
- ตรวจแล้ว N operation: HIGH x, MEDIUM y, LOW z, OK w

## ตารางความเสี่ยง
| # | Operation | หมวด | ระดับ | ปัญหา | วิธีลดความเสี่ยง |
|---|-----------|------|-------|-------|------------------|

## ตรวจข้อมูลก่อนรัน
- query ที่ควรรันและผลที่ยอมรับได้ (เช่น หาค่าซ้ำก่อนเพิ่ม UNIQUE)

## เช็กลิสต์ก่อนรัน
- [ ] สำรองข้อมูล/snapshot
- [ ] ทดสอบบน staging ที่มีข้อมูลขนาดใกล้เคียงจริง
- [ ] ลำดับ deploy โค้ดกับ migration
- [ ] ช่วงเวลาที่ล็อกได้ / คนที่เฝ้า

## แผนถอยกลับ
- ถอยได้ไหม ถอยอย่างไร และข้อมูลส่วนไหนที่ถอยแล้วไม่กลับมา

## สิ่งที่ไฟล์นี้บอกไม่ได้
- รายการสิ่งที่ต้องไปตรวจเพิ่ม
```
