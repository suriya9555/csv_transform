import streamlit as st
import pandas as pd
import re
from io import StringIO, BytesIO
import chardet
import csv

st.set_page_config(page_title="แปลงไฟล์รายงานรถ", page_icon="🚌")

def clean_value(value):
    """ทำความสะอาดค่าที่มีเครื่องหมาย = และ "" เกินจำเป็น"""
    if pd.isna(value):
        return ""
    cleaned = re.sub(r'^="|"$', '', str(value).strip())
    cleaned = re.sub(r'^"|"$', '', cleaned)
    return cleaned

def detect_delimiter(file_content, encoding):
    """ตรวจจับตัวแบ่งคอลัมน์อัตโนมัติ"""
    sniffer = csv.Sniffer()
    try:
        sample = file_content.decode(encoding)[:1024]
        return sniffer.sniff(sample).delimiter
    except:
        return ','  # ค่าเริ่มต้นถ้าไม่สามารถตรวจจับได้

def read_csv_file(uploaded_file):
    try:
        # ตรวจจับ encoding
        raw_bytes = uploaded_file.read()
        result = chardet.detect(raw_bytes)
        encoding = result['encoding'] if result['encoding'] else 'utf-8'

        # ตรวจจับ delimiter
        delimiter = detect_delimiter(raw_bytes, encoding)

        # แปลงเป็น text buffer
        decoded = raw_bytes.decode(encoding)
        lines = decoded.splitlines()

        # กรองเฉพาะบรรทัดที่มีคอลัมน์เพียงพอ (คาดว่าตารางจริงมีอย่างน้อย 5 คอลัมน์)
        table_lines = [line for line in lines if delimiter in line and len(line.split(delimiter)) >= 5]

        if not table_lines:
            st.warning("ไม่พบข้อมูลตารางที่เหมาะสมในไฟล์")
            return None

        # สร้าง StringIO ใหม่จากข้อมูลที่กรองแล้ว
        clean_csv = StringIO('\n'.join(table_lines))
        df_raw = pd.read_csv(clean_csv, header=None, delimiter=delimiter)

        # ค้นหา header ที่แท้จริง
        for i in range(min(10, len(df_raw))):
            row = df_raw.iloc[i]
            if any('unit_id' in str(cell).lower() for cell in row) and \
               any('ทะเบียน' in str(cell) for cell in row):
                
                df = df_raw[i + 1:].copy()
                df.columns = row

                # ตัดเหลือ 5 คอลัมน์แรก
                df = df.iloc[:, :5]
                df.reset_index(drop=True, inplace=True)
                return df

        st.warning("ไม่พบหัวตารางที่เหมาะสมในไฟล์ CSV")
        return None

    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการอ่านไฟล์ CSV: {e}")
        return None



def transform_data(input_df):
    """แปลง DataFrame ตามรูปแบบที่ต้องการ"""
    results = []
    
    # ตรวจสอบคอลัมน์ และกำหนดค่าเริ่มต้น
    bus_id_col = None
    unit_id_col = None
    chassis_col = None
    
    # ค้นหาชื่อคอลัมน์ที่ต้องการ
    for col in input_df.columns:
        if col is None:
            continue
        col_str = str(col).lower()
        if 'ทะเบียน' in col_str:
            bus_id_col = col
        elif 'unit_id' in col_str:
            unit_id_col = col
        elif 'ตัวถัง' in col_str or 'chassis' in col_str:
            chassis_col = col
    
    # ตรวจสอบว่าพบคอลัมน์ที่จำเป็นหรือไม่
    missing_cols = []
    if bus_id_col is None:
        missing_cols.append("หมายเลขทะเบียน")
    if unit_id_col is None:
        missing_cols.append("unit_id")
    if chassis_col is None:
        missing_cols.append("หมายเลขตัวถัง")
    
    if missing_cols:
        st.error(f"ไม่พบคอลัมน์ที่จำเป็น: {', '.join(missing_cols)}")
        st.write("คอลัมน์ที่พบในไฟล์:", input_df.columns.tolist())
        return None
    
    # ประมวลผลแต่ละแถว
    for index, row in input_df.iterrows():
        try:
            # ตัดเฉพาะหมายเลขทะเบียนก่อนชื่อจังหวัด
            bus_id_raw = clean_value(row[bus_id_col])
            bus_id = bus_id_raw.split()[0] if isinstance(bus_id_raw, str) else bus_id_raw
            
            unit_id = clean_value(row[unit_id_col])
            chassis_no = clean_value(row[chassis_col])
            
            results.append({
                'bus_id': bus_id,
                'unit_id': unit_id,
                'chassis_no': chassis_no
            })
        except Exception as e:
            st.warning(f"เกิดข้อผิดพลาดในแถว {index+1}: {str(e)}")
            continue
    
    return pd.DataFrame(results)

# ส่วนติดต่อผู้ใช้
st.title("🚌 แปลงไฟล์รายงานรถตามสายทาง")
st.markdown("""
เครื่องมือนี้สำหรับแปลงไฟล์ CSV รายงานรถตามสายทาง ให้เหลือเพียงข้อมูลที่จำเป็นคือ:
- `bus_id` (หมายเลขทะเบียน)
- `unit_id` (หมายเลขเครื่อง GPS)
- `chassis_no` (หมายเลขตัวถัง)
""")

uploaded_file = st.file_uploader("เลือกไฟล์ CSV ที่ต้องการแปลง", type=['csv'])

if uploaded_file is not None:
    try:
        # อ่านไฟล์ CSV ด้วยวิธีที่ยืดหยุ่น
        df = read_csv_file(uploaded_file)
        
        if df is not None:
            st.success("อ่านไฟล์สำเร็จ!")
            st.write("ตัวอย่างข้อมูลต้นทาง (5 แถวแรก):")
            st.dataframe(df.head())
            
            # แปลงข้อมูล
            with st.spinner('กำลังแปลงข้อมูล...'):
                transformed_df = transform_data(df)
            
            if transformed_df is not None and not transformed_df.empty:
                st.success("แปลงข้อมูลสำเร็จ!")
                st.write("ตัวอย่างข้อมูลหลังแปลง (5 แถวแรก):")
                st.dataframe(transformed_df.head())
                
                # ดาวน์โหลดไฟล์ผลลัพธ์
                csv = transformed_df.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="ดาวน์โหลดไฟล์ที่แปลงแล้ว",
                    data=csv,
                    file_name='converted_bus_data.csv',
                    mime='text/csv'
                )
            else:
                st.error("ไม่พบข้อมูลที่สามารถแปลงได้")
                
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดร้ายแรง: {str(e)}")
        st.markdown("""
## คำแนะนำในการแก้ไขปัญหา

1. **ตรวจสอบตัวแบ่งคอลัมน์**:
   - ไฟล์ CSV ควรใช้เครื่องหมาย comma (,) เป็นตัวแบ่งคอลัมน์
   - หากใช้ตัวแบ่งอื่น เช่น semicolon (;) ให้บันทึกไฟล์ใหม่โดยใช้ comma

2. **ตรวจสอบการจัดรูปแบบ**:
   - แต่ละแถวควรมีจำนวนคอลัมน์เท่ากัน
   - ข้อมูลที่มี comma ควรอยู่ใน quotes ("...")

3. **วิธีแก้ไขด่วน**:
   - เปิดไฟล์ใน Notepad++ หรือ Excel
   - บันทึกใหม่โดยเลือก "CSV (Comma delimited)"
   - ลองอัปโหลดอีกครั้ง

4. **ตัวอย่างไฟล์ที่ถูกต้อง**:
""")
        st.code("""
#,เส้นทาง,unit_id,หมายเลขทะเบียน,หมายเลขตัวถัง,ยี่ห้อรถ
"1","220 อุดรธานี - เลย","06500030000000AXIS190716014","10-2045 เลย","RV541P45006",HINO
"2","220 อุดรธานี - เลย","033000400200864507036482858","10-1701 เลย","RU638A45908",HINO
""")
