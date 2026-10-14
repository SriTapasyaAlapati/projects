"""
catalog_service/products_data.py
---------------------------------
A small, static in-memory product catalog (stand-in for a real product
database / search index). Every catalog shard imports this SAME full list
and then filters it down, at startup, to just the products the consistent
hash ring assigns to that shard's node_id. This mimics horizontal
partitioning of a catalog/search service.
"""

ALL_PRODUCTS = [
    {"product_id": "P001", "name": "Matte Liquid Lipstick - Rustic",       "category": "Makeup",    "brand": "Nyx Nova",     "price": 499,  "stock": 120},
    {"product_id": "P002", "name": "Hydrating Vitamin C Serum 30ml",       "category": "Skincare",  "brand": "GlowLab",      "price": 899,  "stock": 75},
    {"product_id": "P003", "name": "Charcoal Deep Cleanse Face Wash",      "category": "Skincare",  "brand": "PureEarth",    "price": 349,  "stock": 200},
    {"product_id": "P004", "name": "Argan Oil Hair Serum 100ml",          "category": "Haircare",  "brand": "Silkara",      "price": 599,  "stock": 90},
    {"product_id": "P005", "name": "Eau De Parfum - Midnight Bloom 50ml",  "category": "Fragrance", "brand": "Essenza",      "price": 1999, "stock": 40},
    {"product_id": "P006", "name": "Waterproof Kohl Eyeliner - Black",     "category": "Makeup",    "brand": "Nyx Nova",     "price": 249,  "stock": 300},
    {"product_id": "P007", "name": "SPF 50 PA+++ Sunscreen Gel",           "category": "Skincare",  "brand": "SunShield",    "price": 499,  "stock": 150},
    {"product_id": "P008", "name": "Keratin Smooth Shampoo 340ml",         "category": "Haircare",  "brand": "Silkara",      "price": 449,  "stock": 110},
    {"product_id": "P009", "name": "Compact Powder - Ivory Beige",         "category": "Makeup",    "brand": "VelvetTouch",  "price": 399,  "stock": 130},
    {"product_id": "P010", "name": "Rose Water Facial Toner 200ml",        "category": "Skincare",  "brand": "PureEarth",    "price": 249,  "stock": 180},
    {"product_id": "P011", "name": "Body Mist - Citrus Fields 150ml",      "category": "Fragrance", "brand": "Essenza",      "price": 599,  "stock": 95},
    {"product_id": "P012", "name": "Volumizing Mascara - Jet Black",       "category": "Makeup",    "brand": "VelvetTouch",  "price": 349,  "stock": 140},
    {"product_id": "P013", "name": "Niacinamide 10% Serum 30ml",           "category": "Skincare",  "brand": "GlowLab",      "price": 749,  "stock": 100},
    {"product_id": "P014", "name": "Onion Hair Oil 200ml",                 "category": "Haircare",  "brand": "RootVeda",     "price": 299,  "stock": 210},
    {"product_id": "P015", "name": "Matte Foundation - Sand 30ml",         "category": "Makeup",    "brand": "VelvetTouch",  "price": 699,  "stock": 85},
    {"product_id": "P016", "name": "Aloe Vera Gel 300ml",                  "category": "Skincare",  "brand": "PureEarth",    "price": 199,  "stock": 260},
    {"product_id": "P017", "name": "Perfume Deo Combo - Ocean Breeze",     "category": "Fragrance", "brand": "Essenza",      "price": 349,  "stock": 120},
    {"product_id": "P018", "name": "Anti-Dandruff Hair Conditioner",       "category": "Haircare",  "brand": "RootVeda",     "price": 399,  "stock": 100},
    {"product_id": "P019", "name": "Highlighter Palette - Sunkissed",      "category": "Makeup",    "brand": "Nyx Nova",     "price": 549,  "stock": 70},
    {"product_id": "P020", "name": "Retinol Night Cream 50g",              "category": "Skincare",  "brand": "GlowLab",      "price": 999,  "stock": 60},
]
