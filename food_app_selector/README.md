# Smart Food Delivery App Selector (India)

This project compares **Zomato**, **Swiggy**, and **Magicpin** for a given item/restaurant/location and recommends the best option based on:

* Total cost (item price + delivery fee + taxes - discounts)
* Delivery time (minutes)
* Discount/offers

All amounts are in **Indian Rupees (₹)**.

> Scraping note: Real scraping from Zomato/Swiggy can be blocked by bot protections or dynamic rendering.  
> If scraping fails, the app automatically falls back to deterministic simulated values so the UI still works.

## Folder Structure

```text
food_app_selector/
├── scraper/
│   ├── zomato_scraper.py
│   ├── swiggy_scraper.py
│   ├── magicpin_scraper.py
├── engine/
│   ├── scoring.py
│   ├── weather.py
├── ui/
│   ├── app.py
├── requirements.txt
└── README.md
```

## Setup & Run

```bash
pip install -r requirements.txt
streamlit run ui/app.py
```

From the project root (`food_app_selector/`).

## What to Expect

The UI shows a comparison table (cost/time/discount) and highlights the recommended platform. It also simulates local weather (rainy/cloudy/clear) from your location, adjusts delivery-time estimates accordingly, and shows charts for platform comparison.

