import streamlit as st
import difflib
import html
import requests
from datetime import datetime
import re
import trafilatura
import nltk
from bs4 import BeautifulSoup
import openai

# Ensure nltk punkt tokenizer is downloaded
nltk.download('punkt')

def fetch_available_dates(url):
    try:
        api_url = f"https://web.archive.org/cdx/search/cdx?url={url}&output=json&fl=timestamp&collapse=timestamp:6"
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            dates = [datetime.strptime(item[0], "%Y%m%d%H%M%S").date() for item in data[1:]]
            return dates
    except Exception as e:
        st.error(f"Error fetching available dates: {e}")
    return []

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

def compute_diff(text1, text2):
    if isinstance(text1, list) and isinstance(text2, list):
        diff = difflib.ndiff(text1, text2)
    else:
        diff = difflib.ndiff(text1.splitlines(keepends=True), text2.splitlines(keepends=True))
    return list(diff)

def extract_html_part(html_content, part, include_title_and_meta=False):
    soup = BeautifulSoup(html_content, 'html.parser')
    if part == "Head":
        return str(soup.head) if soup.head else ""
    elif part == "Body":
        return str(soup.body) if soup.body else ""
    elif part == "Extracted Text Content":
        text_content = []
        if include_title_and_meta:
            title_tag = soup.find('title')
            meta_desc_tag = soup.find('meta', attrs={'name': 'description'})
            if title_tag:
                text_content.append(f"title: {title_tag.get_text()}")
            if meta_desc_tag:
                text_content.append(f"meta description: {meta_desc_tag.get('content', '')}")
        extracted_text = trafilatura.extract(html_content, output_format="text")
        if extracted_text:
            text_content.extend(nltk.sent_tokenize(extracted_text))
        return text_content
    return html_content

def pretty_diff(diff, escape_html=True, strip_whitespace=False, format_for_ai=False, show_only_changes=False):
    formatted_diff = []
    line_num_1 = line_num_2 = 0

    for line in diff:
        content = line[2:].strip() if strip_whitespace else line[2:]
        line_indicator = line[0]

        if escape_html:
            content = html.escape(content)

        if line_indicator == ' ':
            if show_only_changes:
                if format_for_ai:
                    continue
                else:
                    # Check if the sentence has any changes
                    if any(change_line[0] in ['+', '-'] for change_line in diff if change_line[2:].strip() == content):
                        formatted_line = f"<span>{content}</span>" if content else "[Blank Line]"
                        formatted_diff.append(formatted_line)
            else:
                line_num_1 += 1
                line_num_2 += 1
                line_prefix = f"{line_num_1}: " if format_for_ai else f"{line_num_1}: "
                if format_for_ai:
                    formatted_line = f"{line_prefix} {content}" if content else f"{line_prefix} [Blank Line]"
                else:
                    formatted_line = f"{line_prefix} {content}" if content else f"{line_prefix} [Blank Line]"
                formatted_diff.append(formatted_line)
        elif line_indicator == '+':
            line_num_2 += 1
            line_prefix = f"+{line_num_2}: " if format_for_ai else f"+{line_num_2}: "
            if format_for_ai:
                formatted_line = f"{line_prefix} {content}" if content else f"{line_prefix} [Blank Line]"
            else:
                formatted_line = f"<span style='background-color: #ddffdd;'>{line_prefix} {content}</span>" if content else f"<span style='background-color: #ddffdd;'>{line_prefix} [Blank Line]</span>"
            formatted_diff.append(formatted_line)
        elif line_indicator == '-':
            line_num_1 += 1
            line_prefix = f"-{line_num_1}: " if format_for_ai else f"-{line_num_1}: "
            if format_for_ai:
                formatted_line = f"{line_prefix} {content}" if content else f"{line_prefix} [Blank Line]"
            else:
                formatted_line = f"<span style='background-color: #ffdddd;'>{line_prefix} {content}</span>" if content else f"<span style='background-color: #ffdddd;'>{line_prefix} [Blank Line]</span>"
            formatted_diff.append(formatted_line)

    return '\n'.join(formatted_diff) if format_for_ai else '<br>'.join(formatted_diff)

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
    
# Streamlit App Structure
st.title("🧠 SEODiff")
st.markdown("## Webpage HTML Diff with Wayback Machine Support")
st.markdown("Created by [Paul Shapiro](https://searchwilderness.com/)")
st.markdown("For an explanation about how to use SEODiff, see this [blog post](https://searchwilderness.com/).")

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

    focus_on_html_part = st.radio("Focus on Part of HTML", ("Full", "Head", "Body", "Extracted Text Content"))
    include_title_and_meta = False
    if focus_on_html_part == "Extracted Text Content":
        include_title_and_meta = st.checkbox("Include Title and Meta Description", value=False)

    show_only_changes = st.checkbox("Show Only Changes", value=False)

    if st.button("Fetch HTML for Comparison"):
        html1 = fetch_archived_page(wayback_url, selected_date_1) if source1_option == "Archived" else fetch_current_page(wayback_url)
        html2 = fetch_archived_page(wayback_url, selected_date_2) if source2_option == "Archived" else fetch_current_page(wayback_url)

        if html1 and html2:
            if focus_on_html_part == "Extracted Text Content":
                st.session_state.text1 = extract_html_part(html1, focus_on_html_part, include_title_and_meta)
                st.session_state.text2 = extract_html_part(html2, focus_on_html_part, include_title_and_meta)
            else:
                st.session_state.text1 = extract_html_part(html1, focus_on_html_part)
                st.session_state.text2 = extract_html_part(html2, focus_on_html_part)

if 'text1' in st.session_state and 'text2' in st.session_state:
    diff = compute_diff(st.session_state.text1, st.session_state.text2)
    pretty_diff_text = pretty_diff(diff, show_only_changes=show_only_changes)
    st.markdown("<div class='scrollable-container'>" + pretty_diff_text + "</div>", unsafe_allow_html=True)

st.header("AI Analysis of Diff")
with st.form("ai_analysis_form"):
    api_key = st.text_input("Enter OpenAI API Key", type="password")
    model_choice = st.selectbox("Choose AI Model", ["gpt-3.5-turbo-16k", "gpt-3.5-turbo", "gpt-4-32k", "gpt-4-turbo", "gpt-4.5-turbo", "gpt-4", "gpt-4-1106-preview"])
    if 'text1' in st.session_state and 'text2' in st.session_state:
        ai_analysis_text = pretty_diff(diff, escape_html=False, strip_whitespace=True, format_for_ai=True, show_only_changes=show_only_changes)
    else:
        ai_analysis_text = ""
    user_prompt = st.text_area("Customize the Prompt", value=f"Analyze the changes as specified from the output via python's difflib, taking into account the included line numbers. A '-' before a line means it was removed. A '+' before a line means it was added. Make sure to note anything that may impact SEO such as canonical, hreflang, schema, links, or content changes. Summarize the results.\n\n{ai_analysis_text}", height=150)
    analyze_button = st.form_submit_button("Analyze Diff")

    if analyze_button and api_key:
        analysis_result = analyze_diff_with_ai(model_choice, user_prompt, api_key)
        st.text_area("Analysis Result", value=analysis_result, height=150)

st.markdown(""" 
    <style>
        .scrollable-container {
            overflow-y: scroll;
            height: 400px; 
            border: 1px solid #ccc; 
            padding: 10px; 
        }
    </style>
    """, unsafe_allow_html=True)