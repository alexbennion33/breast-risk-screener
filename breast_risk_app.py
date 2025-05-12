
import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import os
import json

# Load secrets
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
firebase_key_dict = json.loads(os.getenv("FIREBASE_KEY_JSON"))

# Firebase setup
if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_key_dict)
    firebase_admin.initialize_app(cred)
db = firestore.client()

st.set_page_config(page_title="Advanced Breast Cancer Risk Screener", layout="centered")
st.title("Advanced Breast Cancer Risk Assessment")

score = 0

# Clinical questions and logic
if st.radio("Have you tested positive for BRCA1 or BRCA2?", ["Yes", "No", "Unsure"]) == "Yes":
    score += 10
if st.radio("Do you have a first-degree relative with breast cancer?", ["Yes", "No"]) == "Yes":
    score += 6
if st.radio("Do you have Ashkenazi Jewish ancestry?", ["Yes", "No"]) == "Yes":
    score += 3
if st.radio("Do you have a family history of ovarian cancer?", ["Yes", "No"]) == "Yes":
    score += 3
if st.radio("Do you have a male relative who had breast cancer?", ["Yes", "No"]) == "Yes":
    score += 4
if st.radio("Did you have your first period before age 12?", ["Yes", "No"]) == "Yes":
    score += 3
if st.radio("Were you over 30 at the time of your first full-term pregnancy?", ["Yes", "No", "Not applicable"]) == "Yes":
    score += 2
if st.radio("Have you breastfed for 6+ months total?", ["Yes", "No", "Not applicable"]) == "No":
    score += 2
if st.radio("Have you ever used hormone replacement therapy (estrogen + progestin) for more than 5 years?", ["Yes", "No", "Not sure"]) == "Yes":
    score += 3

bmi = st.number_input("What is your Body Mass Index (BMI)?", min_value=10.0, max_value=60.0, step=0.1)
if bmi > 30:
    score += 2
if st.radio("Do you consume alcohol most days (1+ drinks/day)?", ["Yes", "No"]) == "Yes":
    score += 2
if st.radio("Do you engage in less than 90 minutes of physical activity per week?", ["Yes", "No"]) == "Yes":
    score += 2
if st.radio("Have you ever been told you have dense breasts?", ["Yes", "No"]) == "Yes":
    score += 4
if st.radio("Have you ever had a breast biopsy?", ["Yes", "No"]) == "Yes":
    score += 3
if st.radio("Have you noticed new redness, swelling, or thickening in one breast?", ["Yes", "No"]) == "Yes":
    score += 8
if st.radio("Have these symptoms lasted more than 1 week?", ["Yes", "No"]) == "Yes":
    score += 2
if st.radio("Have you delayed seeing a provider due to cost, fear, or transportation?", ["Yes", "No"]) == "Yes":
    score += 2
if st.radio("Do you identify as African American?", ["Yes", "No"]) == "Yes":
    score += 2

zip_code = st.text_input("Enter your ZIP code (for provider lookup):")

# Risk gauge
def show_risk_gauge(score):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Your Risk Score"},
        gauge={
            'axis': {'range': [0, 50]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, 9], 'color': "lightgreen"},
                {'range': [10, 19], 'color': "yellow"},
                {'range': [20, 50], 'color': "red"}
            ],
            'threshold': {
                'line': {'color': "black", 'width': 4},
                'thickness': 0.75,
                'value': score
            }
        }
    ))
    st.plotly_chart(fig, use_container_width=True)

# Firebase save
def store_user_risk(zip_code, score):
    data = {
        "zip_code": zip_code,
        "risk_score": score,
        "timestamp": datetime.utcnow().isoformat()
    }
    db.collection("risk_assessments").add(data)

# Google Maps API logic
def geocode_zip(zip_code, api_key):
    geo_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={zip_code}&key={api_key}"
    response = requests.get(geo_url).json()
    if response["results"]:
        location = response["results"][0]["geometry"]["location"]
        return location["lat"], location["lng"]
    else:
        return None, None

def get_nearby_providers(zip_code, api_key, keyword="breast specialist"):
    lat, lng = geocode_zip(zip_code, api_key)
    if not lat:
        return []

    places_url = (
        f"https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        f"?location={lat},{lng}&radius=15000&type=doctor&keyword={keyword}&key={api_key}"
    )
    response = requests.get(places_url).json()
    return response.get("results", [])

def show_provider_list(providers):
    if not providers:
        st.info("No local providers found.")
        return
    for p in providers[:3]:
        name = p.get("name", "Unknown")
        address = p.get("vicinity", "Address not available")
        rating = p.get("rating", "N/A")
        st.markdown(f"**{name}**  \n{address}  \n⭐ {rating} stars")

if st.button("Calculate My Risk"):
    st.subheader("Risk Assessment Result")
    st.write(f"**Your Total Risk Score:** {score}")

    if score <= 9:
        st.success("Risk Level: Low — Continue routine screenings.")
        st.markdown("**Next Step:** Continue routine screenings and check again next year.")
    elif score <= 19:
        st.warning("Risk Level: Moderate — Consider early screening or a consultation.")
        st.markdown("**Next Step:** Talk to your provider about early screening and breast density.")
    else:
        st.error("Risk Level: High — Please consult a breast specialist or genetic counselor.")
        st.markdown("**Next Step:** Schedule a visit with a breast specialist or genetic counselor.")

    show_risk_gauge(score)

    if zip_code:
        store_user_risk(zip_code, score)
        st.subheader("Recommended Providers Near You")
        providers = get_nearby_providers(zip_code, GOOGLE_API_KEY)
        show_provider_list(providers)

    st.caption("Disclaimer: This tool is educational and does not replace medical advice.")
