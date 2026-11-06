# migration-safety-review

AI Skill สำหรับตรวจไฟล์ migration ของฐานข้อมูลก่อนที่คนจะรันจริง ทำงานแบบอ่านและวิเคราะห์อย่างเดียว ไม่รันคำสั่งที่แก้ฐานข้อมูล

รายงานที่ได้: ตารางความเสี่ยงรายคำสั่ง (HIGH / MEDIUM / LOW / OK), query ตรวจข้อมูลก่อนรัน, เช็กลิสต์ก่อนรัน, แผนถอยกลับ และรายการสิ่งที่ไฟล์บอกไม่ได้

## เอกสารหลัก

อ่านวิธีติดตั้ง วิธีใช้ ผลทดสอบ และข้อจำกัดที่ [.claude/skills/migration-safety-review/README.md](.claude/skills/migration-safety-review/README.md)

## โครงสร้างโปรเจกต์

| ที่อยู่ | คืออะไร |
|--------|---------|
| [.claude/skills/migration-safety-review/SKILL.md](.claude/skills/migration-safety-review/SKILL.md) | ตัว Skill |
| [.claude/skills/migration-safety-review/references/risk-checklist.md](.claude/skills/migration-safety-review/references/risk-checklist.md) | เช็กลิสต์ความเสี่ยงที่ Skill อ้างอิง |
| [.claude/skills/migration-safety-review/examples/test-cases.md](.claude/skills/migration-safety-review/examples/test-cases.md) | ชุดทดสอบและเฉลย (ห้ามให้ AI ที่ถูกทดสอบเห็น) |
| [fixtures/](fixtures/) | ไฟล์ migration ตัวอย่าง 5 เคส ใช้อ่านอย่างเดียว ห้ามรันกับฐานข้อมูล |
| [evaluation/](evaluation/) | ผลดิบของการทดสอบ AI ปกติ (A) เทียบ AI + Skill (B) และ [MANUAL_STEPS.md](evaluation/MANUAL_STEPS.md) |

## สรุปผลทดสอบ

5 เคส เคสละ 1 รอบ ไฟล์เดียวกัน prompt เดียวกัน เทียบ AI ปกติ กับ AI + Skill

| เกณฑ์ | AI ปกติ | AI + Skill |
|-------|---------|------------|
| เจอความเสี่ยงที่ฝังไว้ | 11/11 | 11/11 |
| ระดับความรุนแรงตรงเฉลย | 8/11 | 10/11 |
| แผนถอยกลับครบ | 2/5 | 5/5 |
| บอกสิ่งที่ไฟล์ยืนยันไม่ได้ | 3/5 | 5/5 |
| false positive ที่เคสปลอดภัย | 0 | 0 |

ข้อสรุป: Skill ไม่ได้จับความเสี่ยงได้มากกว่า AI ปกติ ข้อดีคือรายงานมีโครงสร้างสม่ำเสมอ (query ตรวจข้อมูล แผนถอยกลับ และสิ่งที่ยังไม่รู้)

## ข้อจำกัด

ทดสอบรอบเดียวต่อเคส ให้คะแนนโดยผู้สร้าง Skill ไม่ได้ปิดตา ทดสอบเฉพาะ Django และ PostgreSQL และเรียก Skill ด้วยชื่อ ไม่ใช่การรับประกันว่า migration ปลอดภัย รายละเอียดอยู่ในหัวข้อผลทดสอบของ README ใน skill
