from google.cloud import firestore
import os

os.environ["GOOGLE_CLOUD_PROJECT"] = "remitiq-agent"
db = firestore.Client(project="remitiq-agent", database="remitiq-db")

corridors = {
    "PK": {
        "corridor": "PK",
        "regulator_dest": "SBP",
        "zero_fee_threshold_usd": 100,
        "mwallet_incentive_pkr_per_usd": 2.0,
        "mwallet_providers": ["JazzCash", "EasyPaisa", "NayaPay"],
        "settlement_urban_hours": 48,
        "settlement_rural_hours": 96,
        "kyc_docs": ["CNIC", "NICOP", "Passport"],
        "sohni_dharti": True,
        "aml_threshold_usd": 10000,
        "trusted_sources": ["sbp.org.pk", "ecap.org.pk"],
        "disclaimer": "Rates per SBP EPD Circular 2024-25. Verify with your MTO."
    },
    "PH": {
        "corridor": "PH",
        "regulator_dest": "BSP",
        "key_regulation": "BSP Circular 471",
        "philsys_id": True,
        "owwa_coverage": True,
        "receive_channels": ["GCash", "Maya", "LandBank", "BDO", "BPI"],
        "gcash_limit_php": 100000,
        "maya_limit_php": 100000,
        "kyc_docs": ["PhilSys ID", "Passport", "UMID"],
        "aml_threshold_usd": 10000,
        "trusted_sources": ["bsp.gov.ph", "gcash.com", "maya.ph"],
        "disclaimer": "Rates per BSP Reference Rate. Verify with provider."
    },
    "ID": {
        "corridor": "ID",
        "regulator_dest": "Bank Indonesia (BI)",
        "key_regulations": ["BI-FAST", "SNAP API", "QRIS"],
        "kyc_docs": ["KTP", "Passport", "KITAS"],
        "receive_channels": ["BRI", "BNI", "Mandiri", "GoPay", "Dana", "OVO"],
        "bi_fast_limit_idr": 250000000,
        "ewallet_limit_idr": 20000000,
        "aml_threshold_idr": 100000000,
        "bp2mi_fee_waiver": True,
        "trusted_sources": ["bi.go.id", "ojk.go.id"],
        "disclaimer": "Kurs bersifat indikatif. Sumber: bi.go.id."
    },
    "BD": {
        "corridor": "BD",
        "regulator_dest": "Bangladesh Bank (BB)",
        "kyc_docs": ["NID", "Passport", "Smart Card"],
        "receive_channels": ["bKash", "Nagad", "Rocket", "Islami Bank"],
        "bkash_limit_bdt": 200000,
        "nagad_limit_bdt": 200000,
        "cash_incentive_pct": 2.5,
        "wage_earner_bond_rate_pct": 7.5,
        "aml_threshold_usd": 10000,
        "trusted_sources": ["bangladesh-bank.org", "bkash.com"],
        "disclaimer": "Rates indicative. Source: bangladesh-bank.org."
    },
    "UAE_SOURCE": {
        "corridor": "UAE_SOURCE",
        "regulator": "CBUAE",
        "kyc_docs": ["Emirates ID", "Passport", "Residency Visa"],
        "wps_mandatory": True,
        "cash_limit_aed": 3500,
        "aml_threshold_aed": 55000,
        "best_days": "Tuesday-Thursday",
        "licensed_channels": ["Al Ansari", "LuLu Exchange", "Al Fardan", "Wise", "Remitly"],
        "trusted_sources": ["centralbank.ae"],
        "disclaimer": "Rates indicative. Source: centralbank.ae."
    },
    "KSA_SOURCE": {
        "corridor": "KSA_SOURCE",
        "regulator": "SAMA",
        "kyc_docs": ["Iqama", "Passport", "Mada Card"],
        "expat_levy_sar_per_dependent": 400,
        "cash_limit_sar": 5000,
        "stc_pay_daily_sar": 15000,
        "aml_threshold_sar": 60000,
        "best_days": "Sunday-Wednesday",
        "licensed_channels": ["Al Rajhi", "STC Pay", "Urpay", "Wise", "Remitly"],
        "trusted_sources": ["sama.gov.sa"],
        "disclaimer": "Rates indicative. Source: sama.gov.sa."
    }
}

print("Uploading corridor rules to Firestore...")
for corridor_id, rules in corridors.items():
    db.collection("corridor_rules").document(corridor_id).set(rules)
    print(f"✅ {corridor_id} uploaded")

print("\n✅ All corridor rules uploaded to Firestore!")
print(f"Total corridors: {len(corridors)}")
