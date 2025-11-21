import streamlit as st
import pandas as pd
import barcode
from barcode.writer import ImageWriter
import io
import datetime
import firebase_admin
from firebase_admin import credentials, firestore

# --- Configuration ---
st.set_page_config(
    page_title="Event Registration",
    page_icon="🎟️",
    layout="centered"
)

# --- Firebase Initialization ---
# Check if app is already initialized to avoid errors on rerun
if not firebase_admin._apps:
    # Try to get secrets from Streamlit secrets
    if "firebase" in st.secrets:
        # Create a dictionary from the secrets object
        # st.secrets["firebase"] should contain the JSON structure
        cred_dict = dict(st.secrets["firebase"])
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    else:
        st.error("Firebase credentials not found! Please add them to .streamlit/secrets.toml or Streamlit Cloud Secrets.")
        st.stop()

db = firestore.client()

# --- Database Functions (Firebase) ---

def register_user(name, emp_id, gender, email):
    """Register a new user in Firestore. Returns (success, message)."""
    try:
        doc_ref = db.collection('registrations').document(emp_id)
        doc = doc_ref.get()
        
        if doc.exists:
            return False, "This Employee ID is already registered."
        
        # Create new document
        doc_ref.set({
            'name': name,
            'emp_id': emp_id,
            'gender': gender,
            'email': email,
            'download_count': 0,
            'created_at': firestore.SERVER_TIMESTAMP
        })
        return True, "Registration successful!"
    except Exception as e:
        return False, f"An error occurred: {e}"

def get_stats():
    """Fetch statistics from Firestore."""
    try:
        # Stream all documents (efficient for small-medium datasets)
        # For large datasets, consider using aggregation queries or counters
        docs = db.collection('registrations').stream()
        
        data = []
        for doc in docs:
            data.append(doc.to_dict())
            
        df = pd.DataFrame(data)
        
        if df.empty:
            return 0, 0, pd.Series(dtype=int)
            
        total_registrations = len(df)
        total_downloads = df['download_count'].sum()
        gender_counts = df['gender'].value_counts()
        
        return total_registrations, total_downloads, gender_counts
    except Exception as e:
        st.error(f"Failed to fetch stats: {e}")
        return 0, 0, pd.Series(dtype=int)

def increment_download(emp_id):
    """Increment the download count for a user."""
    try:
        doc_ref = db.collection('registrations').document(emp_id)
        doc_ref.update({'download_count': firestore.Increment(1)})
    except Exception as e:
        print(f"Error updating download count: {e}")

def generate_barcode(emp_id):
    """Generate a barcode image in memory."""
    code128 = barcode.get_barcode_class('code128')
    my_barcode = code128(emp_id, writer=ImageWriter())
    buffer = io.BytesIO()
    my_barcode.write(buffer)
    buffer.seek(0)
    return buffer

# --- Main App ---
def main():
    st.title("🎟️ Event Registration")
    
    # Sidebar Navigation
    menu = ["Registration", "Admin Dashboard"]
    choice = st.sidebar.radio("Menu", menu)
    
    if choice == "Registration":
        st.header("User Registration")
        st.write("Please fill in your details to generate your event pass.")
        
        with st.form("reg_form"):
            name = st.text_input("Full Name", placeholder="John Doe")
            emp_id = st.text_input("Employee ID", placeholder="EMP12345")
            email = st.text_input("Email Address", placeholder="john@example.com")
            gender = st.radio("Gender", ["Male", "Female", "Other"], horizontal=True)
            
            submitted = st.form_submit_button("Generate Pass")
            
        if submitted:
            if name and emp_id and email and gender:
                success, msg = register_user(name, emp_id, gender, email)
                if success:
                    st.success(f"🎉 {msg}")
                    # Store in session state to persist the barcode view
                    st.session_state['last_emp_id'] = emp_id
                    st.session_state['show_barcode'] = True
                else:
                    st.error(msg)
            else:
                st.warning("Please fill in all fields.")
        
        # Show Barcode if registered
        if st.session_state.get('show_barcode') and st.session_state.get('last_emp_id'):
            emp_id = st.session_state['last_emp_id']
            st.divider()
            st.subheader("Your Event Pass")
            
            # Generate Barcode
            barcode_buffer = generate_barcode(emp_id)
            st.image(barcode_buffer, caption=f"Pass for {emp_id}", width=400)
            
            # Download Button
            st.download_button(
                label="⬇️ Download Barcode",
                data=barcode_buffer,
                file_name=f"{emp_id}.png",
                mime="image/png",
                on_click=increment_download,
                args=(emp_id,)
            )
            
            if st.button("Register Another User"):
                st.session_state['show_barcode'] = False
                st.session_state['last_emp_id'] = None
                st.rerun()

    elif choice == "Admin Dashboard":
        st.header("📊 Admin Dashboard")
        
        if st.button("Refresh Data"):
            st.rerun()
            
        total_reg, total_dl, gender_counts = get_stats()
        
        # Metrics
        col1, col2 = st.columns(2)
        col1.metric("Total Registrations", total_reg)
        col2.metric("Barcodes Downloaded", total_dl)
        
        st.divider()
        
        # Charts
        st.subheader("Gender Distribution")
        if not gender_counts.empty:
            st.bar_chart(gender_counts)
            
            # Show raw data table
            with st.expander("View Raw Data"):
                # Re-fetch for table view is inefficient, but simple. 
                # Ideally we pass the DF from get_stats, but for now this is fine.
                # Let's just use the aggregate data we have or fetch again if needed.
                # For simplicity, we won't show the full table here to save reads, 
                # or we can modify get_stats to return the DF.
                # Let's modify get_stats to be cleaner.
                pass 
        else:
            st.info("No registrations yet.")

if __name__ == '__main__':
    main()
