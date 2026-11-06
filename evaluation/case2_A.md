# ผลตรวจ migration: fixtures/case2_notnull_fk_default_none.py

**สรุป: ยังไม่ควร merge หรือ deploy** พบ 1 ปัญหาร้ายแรงที่ทำให้ migration ล้มบนฐานข้อมูลที่มีข้อมูลอยู่แล้ว (AddField FK แบบ NOT NULL ด้วย `default=None`) และอีก 1 ปัญหาด้านความสอดคล้องของข้อมูล (default ของ `status` ไม่อยู่ใน `choices`)

## ปัญหาที่พบ

### 1. [สูง / บล็อก] AddField `item.base_contract` เป็น FK NOT NULL แต่ `default=None` และ `preserve_default=False`

- field นี้ไม่มี `null=True` และ default เป็น `None` จึงไม่มีค่าให้แถวเดิมของตาราง `item` Django จะไม่ใส่ `DEFAULT` ใน SQL
- ถ้าตาราง `item` มีข้อมูลอยู่ migration จะล้มเหลว เช่น PostgreSQL แจ้งว่า `column "base_contract_id" ... contains null values` ส่วน SQLite แจ้ง `NOT NULL constraint failed`
- migration นี้จะผ่านเฉพาะตารางที่ว่างเท่านั้น DB ของ dev หรือ test ที่ว่างจะผ่านโดยไม่มีใครรู้ตัว แล้วมาล้มบน staging หรือ prod
- รูปแบบนี้มักเกิดตอน `makemigrations` ถามหา one-off default แล้วตอบว่า `None` ซึ่งไม่ใช่ค่าที่ใช้ได้จริง
- `preserve_default=False` แค่ทิ้ง default ออกจาก state หลังรัน migration ไม่ได้ช่วยให้แถวเดิมมีค่า

**วิธีแก้ที่แนะนำ: แบ่งเป็น 3 ขั้น (expand, backfill, contract)**

```python
# 0025_item_base_contract_nullable.py
operations = [
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
]

# 0026_backfill_item_base_contract.py
def backfill(apps, schema_editor):
    Item = apps.get_model("catalog", "Item")
    BaseContract = apps.get_model("contracts", "BaseContract")
    # ตัดสินใจเชิงธุรกิจก่อนว่า item เดิมต้องผูกกับสัญญาไหน
    # เช่น derive จากข้อมูลเดิม หรือสร้างสัญญา legacy/placeholder
    legacy, _ = BaseContract.objects.get_or_create(...)  # ใส่ field จริงของ model
    Item.objects.filter(base_contract__isnull=True).update(base_contract=legacy)

operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]

# 0027_item_base_contract_not_null.py
operations = [
    migrations.AlterField(
        model_name="item",
        name="base_contract",
        field=models.ForeignKey(
            on_delete=django.db.models.deletion.PROTECT,
            related_name="items",
            to="contracts.basecontract",
        ),
    ),
]
```

ข้อควรระวัง

- ต้องตัดสินใจเรื่อง business ก่อนว่า item เดิมควรผูกกับ `BaseContract` ตัวไหน ถ้าตอบไม่ได้ ให้พิจารณาปล่อยเป็น `null=True` ถาวรและแก้ model ให้ตรงกัน
- ควรแยกเป็นไฟล์ migration คนละไฟล์ เพราะบน PostgreSQL การทำ data update แล้ว `ALTER TABLE` ในทรานแซกชันเดียวกันอาจเจอ `cannot ALTER TABLE because it has pending trigger events` (มาจาก FK constraint ที่เป็น deferred)
- ถ้าตาราง `item` ใหญ่ ให้ backfill เป็น batch และเช็กผลของ lock ตอนสร้าง index และ FK constraint

### 2. [กลาง] AlterField `stage.status`: `default="pending"` ไม่อยู่ใน `choices`

- `choices` มีเฉพาะ `draft`, `review`, `approved`, `closed` แต่ default เป็น `pending`
- ผลที่ตามมา: `full_clean()`, ModelForm, admin และ DRF serializer จะปฏิเสธ instance ที่ใช้ค่า default และ `get_status_display()` จะคืนค่าดิบ `"pending"`
- ถ้าเดิมมี `pending` อยู่ใน choices แล้วถูกเอาออก แถวเดิมที่มี `status="pending"` จะกลายเป็นค่านอก choices Django ไม่แก้ข้อมูลให้ เพราะ `AlterField` นี้ไม่มี SQL เลย (Django ไม่เก็บ default หรือ choices ไว้ในฐานข้อมูล) migration จึง "ผ่าน" แต่ปัญหายังอยู่
- ทางแก้ มี 2 ทาง เลือกตามความตั้งใจ
  - (ก) เปลี่ยน default ให้เป็นค่าที่อยู่ใน choices เช่น `"draft"`
  - (ข) เพิ่ม `("pending", "Pending")` กลับเข้าไปใน choices
- แล้วตรวจข้อมูลเดิมก่อน deploy เช่น `Stage.objects.exclude(status__in=[...]).values("status").annotate(n=Count("id"))` ถ้ามีค่านอก choices ให้เพิ่ม `RunPython` เพื่อ map ค่าเดิมไปเป็นค่าใหม่

### 3. [ต่ำ / ข้อสังเกต] RenameField `item.old_name` เป็น `new_name`

- ตัว operation เขียนถูกต้องและ reverse ได้ ไม่มีปัญหาในตัวเอง
- สิ่งที่ต้องยืนยัน
  - `old_name` มีอยู่จริงใน state ณ migration 0024
  - ไม่มี code, serializer, query, raw SQL, view หรือ index ที่ยังอ้างชื่อเดิม
  - เรื่อง zero-downtime: ชื่อคอลัมน์เปลี่ยนทันทีที่ migrate ระหว่าง rolling deploy โค้ดเวอร์ชันเก่าที่ยังรันอยู่จะพัง ถ้าต้อง zero-downtime ให้ใช้ `db_column` คงชื่อคอลัมน์เดิม หรือทำแบบ expand/contract

### 4. [ต่ำ] โครงสร้าง migration

- รวม 3 operation ที่ไม่เกี่ยวกันไว้ในไฟล์เดียว ทำให้ rollback และไล่หาสาเหตุยาก บน MySQL (DDL ไม่อยู่ในทรานแซกชัน) ถ้าล้มกลางทางจะค้างสถานะครึ่งๆ กลางๆ แนะนำให้แยกตามเรื่อง (rename, FK, status)
- dependencies ดูสมเหตุสมผลจากเนื้อไฟล์ แต่ต้องยืนยันว่า `0024_item_stage` เป็น leaf ล่าสุดของ `catalog` (ไม่มี leaf node ซ้อน) และ model `Stage` อยู่ใน app `catalog`

## ส่วนที่ไม่มีปัญหา

- `on_delete=PROTECT` เหมาะกับความสัมพันธ์ระหว่าง item กับสัญญา (ป้องกันลบสัญญาที่ยังมี item ผูกอยู่)
- ทุก operation reverse ได้
- `max_length=20` เพียงพอสำหรับทุก choice

## ข้อจำกัดของการตรวจ

ตรวจจากเนื้อไฟล์ที่ส่งมาเท่านั้น ยังไม่ได้ดู `models.py`, migration ก่อนหน้า, ขนาดและเนื้อหาข้อมูลจริง หรือชนิด DB ที่ใช้ ข้อสรุปข้อ 1 อิงพฤติกรรมของ Django กับ PostgreSQL และ SQLite

## Checklist ก่อน merge

- [ ] แก้ AddField เป็นแบบ nullable, backfill, แล้วค่อย NOT NULL
- [ ] ตัดสินใจและกำหนดค่า `base_contract` ของ item เดิม
- [ ] แก้ default ของ `status` ให้อยู่ใน choices (หรือเพิ่ม `pending` ใน choices) และ map ข้อมูลเดิมถ้ามี
- [ ] ยืนยันว่าไม่มีโค้ดอ้าง `old_name` และวางแผนเรื่อง deploy
- [ ] ทดสอบ migrate ไปข้างหน้าและย้อนกลับบน DB ที่มีข้อมูลตัวอย่าง ไม่ใช่ DB ว่าง
