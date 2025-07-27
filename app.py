from flask import Flask, request, jsonify, render_template
import urllib.request
import urllib.parse
import json
import requests
from sec_api import QueryApi

app = Flask(__name__)

# SEC API 키 설정
queryApi = QueryApi(api_key="f4b4d3051c52e045996c6254be99f8a35b05abdcc7275e84fee6d907f1b859a1")  # ← 여기에 본인 키 입력

# 네이버 뉴스 검색 함수
def get_news(stock_name):
    client_id = "m9EvNrqfBLe4p8Pe615t"
    client_secret = "JR3mg3r8G9"

    query = urllib.parse.quote(stock_name)
    url = f"https://openapi.naver.com/v1/search/news.json?query={query}&display=5&start=1&sort=date"

    request_obj = urllib.request.Request(url)
    request_obj.add_header("X-Naver-Client-Id", client_id)
    request_obj.add_header("X-Naver-Client-Secret", client_secret)

    try:
        response = urllib.request.urlopen(request_obj)
        rescode = response.getcode()
        if rescode == 200:
            response_body = response.read()
            news_data = json.loads(response_body.decode('utf-8'))
            result = []
            for item in news_data['items']:
                result.append({
                    "title": item['title'],
                    "link": item['link'],
                    "description": item['description']
                })
            return result
        else:
            return [{"error": f"API Error Code: {rescode}"}]
    except Exception as e:
        return [{"error": str(e)}]

# SEC 공시 검색 함수
def get_sec_filings(ticker):
    query = {
        "query": f"ticker:{ticker} AND (formType:\"10-K\" OR formType:\"10-Q\")",
        "from": "0",
        "size": "5",
        "sort": [{"filedAt": {"order": "desc"}}]
    }
    try:
        filings = queryApi.get_filings(query)
        result = []
        for f in filings.get('filings', []):
            result.append({
                "formType": f.get('formType', 'N/A'),
                "filedAt": f.get('filedAt', 'N/A'),
                "title": f.get('title', '제목 없음'),
                "link": f.get('linkToFilingDetails', '#')
            })
        return result
    except Exception as e:
        return [{"error": str(e)}]
    
def get_financials(ticker):
    try:
        # CIK 코드 조회
        cik_res = requests.get(f"https://api.sec-api.io?token=YOUR_SEC_API_KEY&ticker={ticker}")
        cik = cik_res.json().get("cik")
        if not cik:
            return {"error": "CIK not found"}

        # XBRL 데이터 조회
        xbrl_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(xbrl_url, headers=headers)
        data = res.json()

        facts = data.get("facts", {}).get("us-gaap", {})

        def get_latest_value(field):
            values = facts.get(field, {}).get("units", {}).get("USD", [])
            if not values:
                return None
            latest = sorted(values, key=lambda x: x.get("end", ""), reverse=True)[0]
            return latest.get("val")

        assets = get_latest_value("Assets")
        net_income = get_latest_value("NetIncomeLoss")
        eps = get_latest_value("EarningsPerShareBasic")
        equity = get_latest_value("StockholdersEquity")

        roe = None
        if net_income and equity:
            try:
                roe = round((net_income / equity) * 100, 2)
            except:
                roe = None

        return {
            "Assets": f"{assets:,}" if assets else "N/A",
            "NetIncome": f"{net_income:,}" if net_income else "N/A",
            "EPS": f"{eps:.2f}" if eps else "N/A",
            "ROE": f"{roe}%" if roe is not None else "N/A"
        }

    except Exception as e:
        return {"error": str(e)}


# 티커 매핑 + 직접 입력 허용
def resolve_ticker(stock_name):
    ticker_map = {
        "팔란티어": "PLTR",
        "테슬라": "TSLA",
        "애플": "AAPL",
        "마이크로소프트": "MSFT",
        "엔비디아": "NVDA"
    }
    return ticker_map.get(stock_name.lower()) or stock_name.upper()

# 기본 페이지
@app.route("/")
def index():
    return render_template("index.html")

# 뉴스 + 공시 통합 API
@app.route("/get_news", methods=["POST"])
def get_news_route():
    data = request.get_json()
    stock_name = data.get("stock", "")
    news = get_news(stock_name)

    ticker = resolve_ticker(stock_name)
    filings = get_sec_filings(ticker) if ticker else []
    financials = get_financials(ticker) if ticker else {}

    return jsonify({"news": news, "filings": filings, "financials": financials})

if __name__ == "__main__":
    app.run(debug=True)