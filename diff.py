import streamlit as st
import difflib
import html
import requests
from datetime import datetime
import openai

def fetch_available_dates(url):
    try:
        api_url = f"https://web.archive.org/cdx/search/cdx?url={url}&output=json&fl=timestamp&collapse=timestamp:6"
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            dates = [datetime.strptime(item[0], "%Y%m%d%H%M%S").date() for item in data[1:]]  # Skip headers
            return dates
    except Exception as e:
        st.error(f"Error fetching available dates: {e}")
    return []

@st.cache_data
def fetch_archived_page(url, date):
    formatted_date = date.strftime("%Y%m%d")
    api_url = f"https://web.archive.org/web/{formatted_date}id_/{url}"
    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            return response.text
    except Exception as e:
        st.error(f"Error fetching archived page: {e}")
    return None

def fetch_current_page(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.text
        else:
            st.error("Failed to fetch the current version of the page.")
    except Exception as e:
        st.error(f"Error fetching current page: {e}")
    return None

@st.cache_data
def compute_diff(text1, text2):
    diff = difflib.ndiff(text1.splitlines(keepends=True), text2.splitlines(keepends=True))
    return list(diff)

def pretty_diff(diff, escape_html=True, strip_whitespace=False, format_for_ai=False):
    formatted_diff = []
    line_num_1 = line_num_2 = 0

    for line in diff:
        content = html.escape(line[2:]) if escape_html else line[2:]
        if strip_whitespace:
            content = content.strip()

        line_indicator = line[0]

        line_num_str = f"{line_num_1:4}" if line_indicator != '+' else f"{line_num_2:4}"
        if format_for_ai:
            line_num_str = str(line_num_1) if line_indicator != '+' else str(line_num_2)

        if line_indicator == '+':
            line_num_2 += 1
            formatted_diff.append(f'<span style="background-color: #ddffdd;">{line_num_str}: {content}</span>')
        elif line_indicator == '-':
            line_num_1 += 1
            formatted_diff.append(f'<span style="background-color: #ffdddd;">{line_num_str}: {content}</span>')
        else:
            line_num_1 += 1
            line_num_2 += 1
            formatted_diff.append(f'{line_num_str}: {content}')

    return '<br>'.join(formatted_diff)

def analyze_diff_with_ai(model, prompt, api_key):
    openai.api_key = api_key
    try:
        response = openai.ChatCompletion.create(
            model=model,
            messages=[{"role": "system", "content": "You are a helpful assistant."}, 
                      {"role": "user", "content": prompt}]
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        return f"An error occurred: {e}"

st.title("🧠 SEODiff")
st.markdown("## Webpage HTML Diff with Wayback Machine Support")
st.markdown("Created by [Paul Shapiro](https://searchwilderness.com/)")

with st.sidebar:
    st.title("Comparison Settings")
    wayback_url = st.text_input("Enter URL for Comparison")

    available_dates = fetch_available_dates(wayback_url) if wayback_url else []

    st.header("HTML Source 1 Options")
    source1_option = st.radio("Choose Source 1 Type", ("Archived", "Current"), key='source1_option')
    selected_date_1 = st.selectbox("Select Date for Source 1", available_dates, key='selected_date_1') if source1_option == "Archived" and available_dates else None

    st.header("HTML Source 2 Options")
    source2_option = st.radio("Choose Source 2 Type", ("Archived", "Current"), key='source2_option')
    selected_date_2 = st.selectbox("Select Date for Source 2", available_dates, key='selected_date_2') if source2_option == "Archived" and available_dates else None

    if st.button("Fetch HTML for Comparison"):
        html1 = fetch_archived_page(wayback_url, selected_date_1) if source1_option == "Archived" else fetch_current_page(wayback_url)
        html2 = fetch_archived_page(wayback_url, selected_date_2) if source2_option == "Archived" else fetch_current_page(wayback_url)
        if html1 and html2:
            st.session_state.text1 = html1
            st.session_state.text2 = html2

pretty_diff_text = ""
if 'text1' in st.session_state and 'text2' in st.session_state:
    diff = compute_diff(st.session_state.text1, st.session_state.text2)
    pretty_diff_text = pretty_diff(diff)
    st.markdown("<div class='scrollable-container'>" + pretty_diff_text + "</div>", unsafe_allow_html=True)

    ai_analysis_text = pretty_diff(diff, escape_html=False, strip_whitespace=True, format_for_ai=True).replace('<br>', '\n')

    st.header("AI Analysis of Diff")
    with st.form("ai_analysis_form"):
        api_key = st.text_input("Enter OpenAI API Key", type="password")
        model_choice = st.selectbox("Choose AI Model", ["gpt-3.5-turbo-16k", "gpt-4-32k", "gpt-4-turbo", "gpt-4-1106-preview"])
        user_prompt = st.text_area("Customize the Prompt", value=f"Analyze the changes as specified from the output via python's difflib, taking into account the included line numbers. Summarize the results.\n\n{ai_analysis_text}", height=150)
        analyze_button = st.form_submit_button("Analyze Diff")

        if analyze_button and api_key:
            analysis_result = analyze_diff_with_ai(model_choice, user_prompt, api_key)
            st.text_area("Analysis Result", value=analysis_result, height=150)

st.markdown("""
    <style>
        .scrollable-container {
            overflow-y: scroll;
            height: 400px;
        }
    </style>
    """, unsafe_allow_html=True)