# create_mock_data.py
# Creates fake news articles that look exactly like
# what the real fetchers would produce.
# Run this once to set up test data.

import pandas as pd
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Africa/Lagos timezone — same as the real fetchers use
WAT = timezone(timedelta(hours=1))

def wat(hour, minute=0):
    return datetime(2026, 5, 20, hour, minute, tzinfo=WAT)

# ── Matches ARTICLE_COLUMNS from base.py exactly ──
mock_articles = [

    # ── BusinessDay articles ──
    {
        "published_date"   : wat(8, 0),
        "source"           : "businessday",
        "headline"         : "Zenith Bank reports strong Q2 profit beating analyst estimates",
        "article_text"     : "Zenith Bank Plc has reported a strong second quarter profit that beat analyst estimates by 12 percent. The bank attributed the strong performance to growth in retail banking and digital channels. Net interest income rose significantly compared to the same period last year. The board has approved an interim dividend for shareholders.",
        "url"              : "https://businessday.ng/zenith-bank-q2-profit",
        "mentioned_tickers": [],
    },
    {
        "published_date"   : wat(8, 15),
        "source"           : "businessday",
        "headline"         : "Zenith Bank faces CBN review over foreign exchange handling",
        "article_text"     : "The Central Bank of Nigeria has commenced a review of Zenith Bank's foreign exchange operations following concerns raised by market participants. The review is part of a broader regulatory sweep of tier-one banks. Analysts say the impact on earnings may be limited but the regulatory uncertainty adds short term risk.",
        "url"              : "https://businessday.ng/zenith-bank-cbn-review",
        "mentioned_tickers": [],
    },
    {
        "published_date"   : wat(8, 30),
        "source"           : "businessday",
        "headline"         : "Guaranty Trust reports N500bn profit in H1 2026",
        "article_text"     : "Guaranty Trust Holding Company has posted a profit before tax of N500 billion in the first half of 2026, representing a 34 percent increase year on year. The result was driven by strong non-interest income and improved asset quality. The board declared an interim dividend of N1.50 per share.",
        "url"              : "https://businessday.ng/gtco-h1-profit",
        "mentioned_tickers": [],
    },
    {
        "published_date"   : wat(8, 45),
        "source"           : "businessday",
        "headline"         : "GTBank digital platform crosses 10 million users",
        "article_text"     : "Guaranty Trust Bank's digital banking platform has crossed 10 million active users, making it one of the largest digital banking platforms in West Africa. The milestone was announced at the bank's investor day in Lagos. Management said digital channels now account for over 70 percent of all transactions.",
        "url"              : "https://businessday.ng/gtbank-digital-10m",
        "mentioned_tickers": [],
    },
    {
        "published_date"   : wat(9, 0),
        "source"           : "businessday",
        "headline"         : "MTN Nigeria subscriber base grows 8 percent in H1 2026",
        "article_text"     : "MTN Nigeria has reported subscriber growth of 8 percent in the first half of 2026, reaching 85 million active subscribers. Data revenue grew 42 percent year on year as smartphone penetration increased across Nigeria. The company maintained its full year guidance.",
        "url"              : "https://businessday.ng/mtn-h1-subscribers",
        "mentioned_tickers": [],
    },
    {
        "published_date"   : wat(9, 10),
        "source"           : "businessday",
        "headline"         : "MTN Nigeria faces regulatory pressure over data pricing",
        "article_text"     : "The Nigerian Communications Commission has written to MTN Nigeria requesting justification for recent increases in data bundle prices. Consumer groups have complained that the increases disproportionately affect low income users. MTN said it was engaging with the regulator constructively.",
        "url"              : "https://businessday.ng/mtn-ncc-data-pricing",
        "mentioned_tickers": [],
    },
    {
        "published_date"   : wat(9, 20),
        "source"           : "businessday",
        "headline"         : "Access Holdings raises concern over rising loan defaults",
        "article_text"     : "Access Holdings Plc has flagged rising non-performing loans as a key risk in its mid-year investor update. The group's NPL ratio edged higher in Q2 as some corporate borrowers struggled with the high interest rate environment. Management said provisions had been increased to cover the exposure.",
        "url"              : "https://businessday.ng/access-loan-defaults",
        "mentioned_tickers": [],
    },
    {
        "published_date"   : wat(9, 30),
        "source"           : "businessday",
        "headline"         : "UBA posts strong H1 results driven by retail banking growth",
        "article_text"     : "United Bank for Africa has posted strong first half results underpinned by growth in its retail and SME banking segments across its 20 African markets. Profit before tax rose 28 percent year on year. The pan-African strategy continues to diversify earnings away from Nigeria-specific risks.",
        "url"              : "https://businessday.ng/uba-h1-results",
        "mentioned_tickers": [],
    },
    {
        "published_date"   : wat(9, 40),
        "source"           : "businessday",
        "headline"         : "Dangote Cement volume falls as construction activity slows",
        "article_text"     : "Dangote Cement has reported a decline in sales volumes in the second quarter as construction activity slowed across Nigeria. The company cited high cement prices and reduced government infrastructure spending as key headwinds. Management said it was cutting production costs to defend margins.",
        "url"              : "https://businessday.ng/dangote-cement-volume",
        "mentioned_tickers": [],
    },
    {
        "published_date"   : wat(9, 50),
        "source"           : "businessday",
        "headline"         : "Fidelity Bank shares rise 4 percent on strong Q2 results",
        "article_text"     : "Fidelity Bank shares rose 4 percent on the Nigerian Exchange following the release of strong second quarter results. Profit after tax grew 31 percent year on year driven by higher interest income. The bank said its digital banking platform was gaining market share rapidly.",
        "url"              : "https://businessday.ng/fidelity-bank-q2",
        "mentioned_tickers": [],
    },

    # ── NGX Announcements — pre-tagged tickers ──
    {
        "published_date"   : wat(7, 0),
        "source"           : "ngx_announcements",
        "headline"         : "Zenith Bank Plc — Audited Full Year Results for 2025",
        "article_text"     : "Zenith Bank Plc hereby notifies the Nigerian Exchange and the investing public of the release of its audited full year results for the period ended 31 December 2025. Profit before tax increased by 22 percent to N620 billion. The board has recommended a final dividend of N4.00 per share subject to shareholders approval.",
        "url"              : "https://ngxgroup.com/zenith-bank-fy2025-results",
        "mentioned_tickers": ["ZEN"],
    },
    {
        "published_date"   : wat(7, 15),
        "source"           : "ngx_announcements",
        "headline"         : "MTN Nigeria Communications Plc — Notification of Closed Period",
        "article_text"     : "MTN Nigeria Communications Plc hereby notifies all dealing members and the investing public that its closed period commenced on 1 May 2026 and will end 24 hours after the release of its H1 2026 unaudited results. Directors and insiders are reminded not to deal in the company's shares during this period.",
        "url"              : "https://ngxgroup.com/mtn-closed-period",
        "mentioned_tickers": ["MTN"],
    },
    {
        "published_date"   : wat(7, 30),
        "source"           : "ngx_announcements",
        "headline"         : "Dangote Cement Plc — Board Meeting Notice",
        "article_text"     : "Dangote Cement Plc hereby notifies the Nigerian Exchange that a meeting of the Board of Directors will hold on 28 May 2026 to consider and approve the unaudited Q2 2026 financial statements and to review the dividend policy for the current financial year.",
        "url"              : "https://ngxgroup.com/dangcem-board-notice",
        "mentioned_tickers": ["DANGCEM"],
    },

    # ── Macro headlines — no specific stock ──
    {
        "published_date"   : wat(8, 0),
        "source"           : "businessday",
        "headline"         : "CBN holds interest rate at 26.25 percent as inflation remains elevated",
        "article_text"     : "The Central Bank of Nigeria Monetary Policy Committee has voted to hold the benchmark interest rate at 26.25 percent at its May 2026 meeting. The committee said inflation remained above target despite recent moderation. The decision was unanimous. Analysts had expected a hold given the fragile growth outlook.",
        "url"              : "https://businessday.ng/cbn-rate-hold-may-2026",
        "mentioned_tickers": [],
    },
    {
        "published_date"   : wat(8, 20),
        "source"           : "businessday",
        "headline"         : "NGX All-Share Index gains 1.2 percent as market sentiment improves",
        "article_text"     : "The Nigerian Exchange All-Share Index gained 1.2 percent on Monday as improved investor sentiment drove buying across banking and consumer goods stocks. Market capitalisation rose by N620 billion. Analysts attributed the rally to positive corporate earnings releases and easing inflation expectations.",
        "url"              : "https://businessday.ng/ngx-asi-gains",
        "mentioned_tickers": [],
    },
    {
        "published_date"   : wat(8, 40),
        "source"           : "businessday",
        "headline"         : "Nigeria GDP growth slows to 2.8 percent in Q1 2026 — NBS report",
        "article_text"     : "Nigeria's gross domestic product grew by 2.8 percent in the first quarter of 2026, slowing from 3.4 percent in Q4 2025, according to the National Bureau of Statistics. The services sector remained the largest contributor to growth while the oil sector contracted slightly due to pipeline disruptions.",
        "url"              : "https://businessday.ng/nigeria-gdp-q1-2026",
        "mentioned_tickers": [],
    },
    {
        "published_date"   : wat(9, 0),
        "source"           : "businessday",
        "headline"         : "FX pressure continues as USD to NGN trades at 1587",
        "article_text"     : "The Nigerian naira continued to face pressure against the US dollar in the official market, trading at N1587 per dollar. The FMDQ exchange reported thin liquidity in the official window. Analysts said the CBN's intervention capacity remained constrained by low oil revenues.",
        "url"              : "https://businessday.ng/fx-pressure-may-2026",
        "mentioned_tickers": [],
    },
]

# ── Build DataFrame matching ARTICLE_COLUMNS exactly ──
ARTICLE_COLUMNS = [
    "published_date",
    "source",
    "headline",
    "article_text",
    "url",
    "mentioned_tickers",
]

df = pd.DataFrame(mock_articles, columns=ARTICLE_COLUMNS)

# ── Save as parquet — same format the real fetchers use ──
output_path = Path("data/output/processed/news/mock_articles.parquet")
output_path.parent.mkdir(parents=True, exist_ok=True)
df.to_parquet(output_path, index=False)

print(f"Mock data created successfully")
print(f"Saved to: {output_path}")
print(f"Total articles : {len(df)}")
print(f"Sources        : {df['source'].unique().tolist()}")
print(f"Columns        : {df.columns.tolist()}")
print(f"\nSample headlines:")
for h in df['headline'].tolist():
    print(f"  - {h}")