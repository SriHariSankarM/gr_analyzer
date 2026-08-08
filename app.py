import streamlit as st
import csv
from google import genai

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

st.set_page_config(
    page_title="Goods Receipt Discrepancy Analyzer",
    layout="wide"
)

st.markdown("""
<style>
.st-key-header {
    background-color: #b7cae2;
    padding: 20px;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

header = st.container(key="header")
header.title("Goods Receipt Discrepancy Analyzer", text_alignment="center")
header.markdown("Analyze purchase orders and goods receipts to identify discrepancies.", text_alignment="center")

st.divider()

PO_TAB, GR_TAB, DA_TAB = st.tabs(["**Purchase Order**", "**Goods Receipt**", "**Discrepancy Analysis**"], width = "stretch", height = "stretch")

with open("purchase_orders.csv", newline="", encoding="utf-8-sig") as file:
    reader = csv.DictReader(file)
    columns = reader.fieldnames
    purchase_orders = list(reader)

filter_fields = PO_TAB.multiselect(
    "Filter Purchase Orders By",
    columns,
    max_selections=10,
    placeholder="Choose fields",
    key = '1'
)

filtered_orders = purchase_orders

for field in filter_fields:
    field_values = sorted({
        row[field].strip()
        for row in filtered_orders
        if row[field].strip()
    })

    selected_value = PO_TAB.selectbox(
        f"Select {field}",
        ["ALL"] + field_values,
        key=f"po_filter_{field}"
    )

    if selected_value != "ALL":
        filtered_orders = [
            row for row in filtered_orders
            if row[field].strip() == selected_value
        ]

PO_TAB.dataframe(
    filtered_orders,
    width="stretch",
    hide_index=True
)

PO_TAB.divider()

PO_TAB.subheader("Purchase Order Total")

po_ids = sorted({
    row["PO_ID"].strip()
    for row in purchase_orders
    if row["PO_ID"].strip()
})

total_po_id = PO_TAB.selectbox(
    "Select Purchase Order ID",
    po_ids,
    index=None,
    placeholder="Choose a PO ID",
    key="total_po_id"
)

if total_po_id:
    total_value = sum(
        float(
            row["AMOUNT"]
            .replace("₹", "")
            .replace(",", "")
            .strip()
        )
        for row in purchase_orders
        if row["PO_ID"].strip() == total_po_id
    )

    PO_TAB.metric(
        "Total Purchase Order Value",
        f"₹ {total_value:,.2f}"
    )

with open("goods_receipts.csv", newline="", encoding="utf-8-sig") as file:
    reader = csv.DictReader(file)
    columns = reader.fieldnames
    goods_receipts = list(reader)

filter_fields = GR_TAB.multiselect(
    "Filter Goods Receipts By",
    columns,
    max_selections=10,
    placeholder="Choose fields",
    key = '2'
)

filtered_receipts = goods_receipts

for field in filter_fields:
    field_values = sorted({
        row[field].strip()
        for row in filtered_receipts
        if row[field].strip()
    })

    selected_value = GR_TAB.selectbox(
        f"Select {field}",
        ["ALL"] + field_values,
        key=f"gr_filter_{field}"
    )

    if selected_value != "ALL":
        filtered_receipts = [
            row for row in filtered_receipts
            if row[field].strip() == selected_value
        ]

GR_TAB.dataframe(
    filtered_receipts,
    width="stretch",
    hide_index=True
)

# Read tolerance data
with open("tolerances.csv", newline="", encoding="utf-8-sig") as file:
    tolerances = list(csv.DictReader(file))

DA_TAB.subheader("Discrepancy Analysis")

po_ids = sorted({
    row["PO_ID"].strip()
    for row in purchase_orders
    if row["PO_ID"].strip()
})

selected_da_po = DA_TAB.selectbox(
    "Select Purchase Order ID",
    po_ids,
    index=None,
    placeholder="Choose a PO ID",
    key="da_po"
)

if selected_da_po:

    po_products = [
        row for row in purchase_orders
        if row["PO_ID"].strip() == selected_da_po
    ]

    comparison = []
    analysis_data = []

    for po in po_products:

        ordered_qty = int(po["ORDERED_QTY"].strip())

        delivered_qty = sum(
            int(gr["DELIVERED_QTY"].strip())
            for gr in goods_receipts
            if gr["PO_ID"].strip() == selected_da_po
            and gr["PRODUCT_ID"].strip() == po["PRODUCT_ID"].strip()
        )

        difference = delivered_qty - ordered_qty

        # Fixed comparison table
        comparison.append({
            "PRODUCT_ID": po["PRODUCT_ID"],
            "PRODUCT_NAME": po["PRODUCT_NAME"],
            "ORDERED_QTY": ordered_qty,
            "DELIVERED_QTY": delivered_qty,
            "DIFFERENCE": difference
        })

        # Tolerance check for AI analysis
        tolerance = next(
            (
                row for row in tolerances
                if row["PRODUCT_ID"].strip() == po["PRODUCT_ID"].strip()
            ),
            None
        )

        if tolerance:
            under_tolerance = float(
                tolerance["UNDER_TOL"].strip()
            )

            over_tolerance = float(
                tolerance["OVER_TOL"].strip()
            )

            deviation = (difference / ordered_qty) * 100

            if difference == 0:
                status = "Exact Match"

            elif difference < 0:
                if abs(deviation) <= under_tolerance:
                    status = "Within Tolerance"
                else:
                    status = "Under Delivery - Review Required"

            else:
                if deviation <= over_tolerance:
                    status = "Within Tolerance"
                else:
                    status = "Over Delivery - Review Required"

            analysis_data.append({
                "PRODUCT": po["PRODUCT_NAME"],
                "ORDERED_QTY": ordered_qty,
                "DELIVERED_QTY": delivered_qty,
                "DIFFERENCE": difference,
                "DEVIATION_PERCENT": round(deviation, 2),
                "UNDER_TOLERANCE_PERCENT": under_tolerance,
                "OVER_TOLERANCE_PERCENT": over_tolerance,
                "STATUS": status
            })

    # Existing factual table
    DA_TAB.dataframe(
        comparison,
        width="stretch",
        hide_index=True
    )

    # AI section below the table
    DA_TAB.divider()
    DA_TAB.subheader("AI Analysis")

    if DA_TAB.button(
        "Generate AI Analysis",
        key="generate_ai_analysis"
    ):

        prompt = f"""
You are analysing a goods receipt discrepancy for a procurement process.

Purchase Order ID:
{selected_da_po}

The following results have already been calculated and verified by the application:

{analysis_data}

Do not recalculate or invent any values.

Analyse the purchase order and provide:

1. A short overall assessment of the purchase order.
2. Identify products that are exact matches.
3. Identify discrepancies that are within tolerance.
4. Identify discrepancies that exceed tolerance.
5. Recommend whether the purchase order can proceed or requires review.
6. Clearly mention any product that should be rerouted for review.

Keep the response concise, professional and suitable for an SAP procurement employee.
"""

        try:
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt
            )

            DA_TAB.write(response.text)

        except Exception as error:
            DA_TAB.error(
                f"AI analysis could not be generated: {error}"
            )