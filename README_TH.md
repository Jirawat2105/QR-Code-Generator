# QR Generator 1.1.1

Python GUI สร้าง QR สำหรับ Windows และ Android ธีมมืด พร้อมพรีวิวสด ทำงานภายในอุปกรณ์ ไม่ต้องสมัครสมาชิก และไม่สร้างลิงก์ redirect ที่หมดอายุ

## เริ่มใช้งาน Windows

ถ้าใช้แพ็กเกจที่ build ไว้แล้ว เปิด `dist/QRGenerator/QRGenerator.exe` ได้เลย โดยเก็บโฟลเดอร์ `_internal` ไว้ข้าง EXE ไม่ต้องติดตั้ง Python

สำหรับรันจากซอร์ส ต้องใช้ Python 3.13 แบบ 64-bit

1. ดับเบิลคลิก `setup.bat` เพื่อติดตั้ง dependencies ครั้งแรก
2. ดับเบิลคลิก `run.bat` เพื่อเปิดแอป
3. ใส่ URL แบบ `https://example.com` ปรับแต่ง แล้วกด **Export QR code**

หรือใช้ PowerShell:

```powershell
uv sync
uv run flet run src/main.py
```


## ตั้งค่ารูปแบบสี่เหลี่ยมมุมมนตามตัวอย่าง

1. เลือก **Square Rounded** ที่ Body shape, Eye frame และ Eye ball เม็ด QR จะมีมุมมนและช่องไฟเล็ก ๆ แยกจากกัน
2. ใช้ Ink style **Plain**, Color `#000000` และ Background style **Plain**, สี `#FFFFFF`, Opacity **100%**
3. ตั้ง Rounded corners และ Soft edge เป็น **0** หากต้องการพื้นหลังขาวสี่เหลี่ยมเต็มภาพ
4. เลือกไฟล์โลโก้ต้นฉบับ สำหรับโลโก้ข้อความยาว ให้เปิด **Wide wordmark**, เลือก **Width** และเริ่มสเกลประมาณ **65–70%**
5. เปิด **Reserve space for logo** แล้วเริ่ม Space around logo ที่ **1 module**
6. ตรวจไฟล์ส่งออกและลองสแกนก่อนพิมพ์จริง ลวดลายขึ้นอยู่กับ URL; ไม่มีการรับประกันว่าทุกขนาดโลโก้จะสแกนได้

โหมดปกติจำกัดด้านยาวของโลโก้ไว้ที่ 25% เช่นเดิม ส่วน Wide wordmark จำกัดด้านสั้นไว้ที่ 25% และเว้นแถบขอบ QR 8 modules เพื่อหลีกเลี่ยง timing/finder โดยไม่ยืดหรือบีบภาพ

## ความสามารถ

- บังคับ URL แบบ HTTP/HTTPS และตรวจค่าก่อนส่งออก
- Minimalist ลดจำนวนโมดูลเมื่อทำได้ โดยยังปรับรูปทรง/สี/โลโก้ได้ทั้งหมด ใช้ error correction M เมื่อไม่มีโลโก้ และ H เมื่อมีโลโก้
- Body: Square, Square Rounded, Rounded, Dots, Diamond, Horizontal
- Eye frame: Square, Square Rounded, Rounded, Circle, Leaf
- Eye ball: Square, Square Rounded, Rounded, Circle, Diamond
- สี QR แบบ Plain / Gradient, พาเลตสี, hex และมุมไล่สี
- โลโก้ PNG / JPG / WebP แบบไม่ครอป ไม่ยืด ไม่บีบ; เลือกอ้างอิง Width หรือ Height และปรับเปอร์เซ็นต์
- เปิด/ปิดพื้นที่ว่างใต้โลโก้ และปรับ padding; โลโก้แสดงครบโดยไม่เจาะช่องให้ QR ทะลุ โลโก้ที่ทับจุดจัดแนวตรงกลางจะแสดงคำแนะนำให้ทดสอบสแกน
- Wide wordmark สำหรับโลโก้ข้อความแนวนอนหรือแนวตั้ง ปรับสเกล 5–80% ได้ โดยยังคงสัดส่วนและย่ออัตโนมัติก่อนถึงแถบ timing/finder
- พื้นหลัง Plain / Gradient / รูปภาพ พร้อม opacity, มุมมน, soft edge และ opacity ที่ขอบ
- ความละเอียด 256–8192 px; ส่งออก PNG / SVG / PDF / JPG หรือครบทุกแบบใน ZIP
- Windows ใช้ process pool สูงสุด 2 processes เพื่องานส่งออกหลายไฟล์บนหลาย CPU cores พร้อมกัน โดยจำกัดการใช้ RAM
- Android ใช้ worker threads สูงสุด 4 ตัว งานภาพ native ของ Pillow เช่น resize/composite/filter/encode ทำงานขนานได้โดยไม่บล็อก UI; ขั้นตอน Python ที่ติด GIL ยังมีข้อจำกัด ไม่ใช่ทุกขั้นตอนจะใช้ครบทุกคอร์
- พรีวิว QR วาดเป็น vector path และ gradient shader บน Flutter Canvas โดยเปิด Impeller บน Android เพื่อใช้ GPU เมื่ออุปกรณ์รองรับ ส่วนการสร้างไฟล์ส่งออกทำบน CPU
- Windows และ Android แนวนอน: Preview ซ้าย / Customize ขวา; แนวตั้งเป็นหน้าเลื่อนโดยหัวข้อเลื่อนตามเนื้อหา
- SafeArea สำหรับรอยบาก/แถบระบบ, ปุ่มสัมผัส และ scroll ที่เหมาะกับมือถือ
- ช่อง URL เติม `https://` เมื่อกด Tab บน Windows หรือ Double Space บน Android (รองรับ IME ที่เปลี่ยนเป็น `. ` ด้วย)
- URL เริ่มต้นเป็น `https://example.com`; กดโลโก้แอปเพื่อเปิด Credits: Jirawat Pratuangtip และ github.com/Jirawat2105 แยกบรรทัด

**การคำนวณโลโก้:** เปอร์เซ็นต์อ้างอิงพื้นที่ตัว QR ไม่รวม quiet zone 4 โมดูล เช่น Width 20% คือความกว้างโลโก้เท่ากับ 20% ของความกว้างพื้นที่ QR และคำนวณความสูงตามอัตราส่วนไฟล์ต้นฉบับ เลือก Height เพื่อกลับไปอ้างอิงความสูง ในโหมดปกติ หากด้านใดเกินพื้นที่ปลอดภัย (ด้านยาวสุด 25% ของ QR) จะลดทั้งสองด้านด้วยตัวคูณเดียวกันโดยไม่ครอปหรือเปลี่ยนสัดส่วน พร้อมแจ้งขนาดที่ใช้จริงในพรีวิว โหมด Wide wordmark อนุญาตให้ขยายด้านยาว โดยจำกัดด้านสั้นไว้ที่ 25% และหลีกเลี่ยงแถบ timing/finder ตามรายละเอียดข้างต้น

## รูปแบบไฟล์

| รูปแบบ | รายละเอียด |
|---|---|
| PNG | รองรับ alpha / พื้นหลังโปร่งใส |
| SVG | รูปทรง QR เป็นเวกเตอร์; โลโก้และเอฟเฟกต์พื้นหลังฝังเป็นรูปภาพภายในไฟล์ |
| PDF | ภาพความละเอียดที่เลือก ตั้งเอกสาร 300 dpi และวางบนพื้นขาว |
| JPG | คุณภาพ 97%, พื้นหลังโปร่งใสแปลงเป็นพื้นขาว |

ขอบเบลอใช้กับพื้นหลังเท่านั้น เพื่อให้โมดูล QR ยังคมชัด พื้นหลังมุมมนถูกจำกัดให้ไม่กินเข้าโมดูล QR สีอ่อน รูปพื้นหลัง และโลโก้ใหญ่มีข้อความแจ้งในพรีวิว ควรสแกนบนพื้นหลัง/ขนาดพิมพ์จริงก่อนนำไปใช้งาน

ค่าปรับแต่งอยู่ใน session ปัจจุบัน ยังไม่มีการบันทึกโปรเจกต์อัตโนมัติเมื่อปิดแอปหรือระบบ Android สร้าง activity ใหม่

## Build Android APK

```powershell
uv run flet build apk --yes
```

ไฟล์ APK อยู่ใน `build/apk/` แยกสถาปัตยกรรมและบีบอัด native libraries เพื่อให้ไฟล์เล็กลง:

- `QRGenerator-arm64-v8a.apk`: สำหรับโทรศัพท์ Android 17 แบบ ARM64
- `QRGenerator-x86_64.apk`: สำหรับ emulator / อุปกรณ์ x86_64

รองรับ Android 17 และทดสอบบน API 37 / memory page 16 KB; ใช้ compile/target SDK 36 ตาม Flutter รุ่นที่ล็อกไว้ และ min SDK 24 ใช้ติดตั้งโดยตรง ไม่ต้องมี Python บนมือถือ การ build ต้องใช้ Android SDK/JDK/Flutter และอินเทอร์เน็ตในครั้งแรก ขนาดหลังติดตั้งจะมากกว่าขนาด APK ที่บีบอัด

สำหรับแจกจ่ายรุ่น production ควรตั้ง signing key ของเจ้าของแอปตาม [คู่มือ Flet Android](https://flet.dev/docs/publish/android/) และเก็บ key ไว้สำหรับอัปเดตรุ่นถัดไป

## Build Windows

```powershell
powershell -File scripts/build_windows.ps1
```

ผลลัพธ์อยู่ใน `dist/QRGenerator/` ต้องเก็บไฟล์ข้าง EXE และโฟลเดอร์ `_internal` ไว้ด้วยกัน สคริปต์ใช้พื้นที่ build แยกจาก Android

## Tests — always E2E

```powershell
uv sync --dev
uv run python scripts/check.py
```

หรือดับเบิลคลิก `test.bat` จะรัน regression + E2E พร้อมเปิด/ปิด server ทดสอบให้อัตโนมัติ ผลทดสอบครอบคลุมการอ่าน QR จาก PDF ด้วย

หากต้องการเปิดแอปแบบ web transport เพื่อทดสอบด้วยตนเอง:

```powershell
$env:QRSTUDIO_WEB='1'
uv run python src/main.py
```

จาก PowerShell อีกหน้าต่าง:

```powershell
uv run python scripts/e2e_web.py
```

E2E ใช้ Microsoft Edge headless ทดสอบกรอก URL, Tab shortcut, Credits, Minimalist, รูปทรงตามภาพบั๊ก, โลโก้ auto-fit, อัปโหลด/ดาวน์โหลดจริง และอ่าน QR จาก PNG/JPG/SVG/PDF รวมทั้ง GPU preview กลับด้วย ZXing-C++ ทดสอบแนวตั้ง 390×844 และแนวนอน 844×450 CSS pixels ที่ device pixel ratio 2 ผลลัพธ์อยู่ที่ `test-results/e2e/`

ทดสอบ APK ที่ติดตั้งใน emulator:

```powershell
uv run python scripts/e2e_android.py
```

การทดสอบอัตโนมัติช่วยยืนยันการทำงานบนรูปที่ทดสอบ แต่ไม่รับประกันทุกชุดสี/โลโก้/แสงกล้องของอุปกรณ์จริง
