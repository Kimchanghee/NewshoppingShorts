"""
E2E 전체 플로우: 쿠팡 상품 → 1688/AliExpress에서 영상 있는 상품 찾기 → 영상 다운로드
- 1688 로그인 필요 시 스킵, AliExpress에서 2개로 폴백
- 영상 없는 상품은 건너뜀
"""
import sys, os, json, time, asyncio, urllib.parse, re, requests as req
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sourcing_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def test_e2e_full_manual_runner():
    pytest.skip("Manual E2E script. Run directly: python tests/test_e2e_full.py")


def log(msg):
    print(f"  {msg}")


def similarity_score(name1, name2):
    if not name1 or not name2:
        return 0
    def tokenize(s):
        s = s.lower()
        tokens = set(re.findall(r'[\u4e00-\u9fff]+|[\uac00-\ud7af]+|[a-z]+|\d+', s))
        chars = set()
        for t in list(tokens):
            if re.match(r'[\u4e00-\u9fff]', t):
                for c in t:
                    chars.add(c)
        tokens.update(chars)
        return tokens
    t1 = tokenize(name1)
    t2 = tokenize(name2)
    if not t1 or not t2:
        return 0
    return len(t1 & t2) / len(t1 | t2)


async def extract_video_urls(tab):
    return await tab.evaluate("""
        (() => {
            const videoUrls = new Set();
            document.querySelectorAll('video').forEach(v => {
                if (v.src) videoUrls.add(v.src);
                if (v.currentSrc) videoUrls.add(v.currentSrc);
                v.querySelectorAll('source').forEach(s => { if (s.src) videoUrls.add(s.src); });
            });
            const html = document.documentElement.innerHTML;
            const patterns = [
                /"(https?:\\/\\/[^"]*?\\.mp4[^"]*?)"/g,
                /"videoUrl"\\s*:\\s*"(https?:\\/\\/[^"]+)"/g,
                /"video_url"\\s*:\\s*"(https?:\\/\\/[^"]+)"/g,
                /"contentUrl"\\s*:\\s*"(https?:\\/\\/[^"]+)"/g,
                /(https?:\\/\\/cloud\\.video\\.taobao\\.com[^\\s"']+)/g,
            ];
            patterns.forEach(pattern => {
                let m;
                while ((m = pattern.exec(html)) !== null) { videoUrls.add(m[1]); }
            });
            document.querySelectorAll('script[type="application/ld+json"]').forEach(s => {
                try {
                    const d = JSON.parse(s.textContent);
                    if (d['@type'] === 'VideoObject' && d.contentUrl) videoUrls.add(d.contentUrl);
                } catch(e) {}
            });
            return [...videoUrls].slice(0, 10);
        })()
    """) or []


async def download_video(vurl, filepath, referer):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": referer
        }
        r = req.get(vurl, headers=headers, timeout=30, stream=True)
        if r.status_code == 200:
            total = 0
            with open(filepath, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    total += len(chunk)
            if total < 10000:
                os.remove(filepath)
                return None
            return round(total / (1024 * 1024), 1)
    except Exception as e:
        log(f"    다운로드 에러: {e}")
        if os.path.exists(filepath):
            os.remove(filepath)
    return None


async def find_product_with_video(browser, candidates, source_name, filepath_prefix, max_try=10):
    """후보 리스트에서 영상 있는 첫 번째 상품을 찾아 다운로드. 성공 시 dict 반환, 실패 시 None."""
    tried = 0
    for i, cand in enumerate(candidates[:max_try]):
        detail_url = cand.get("url", "")
        log(f"  [{i+1}] score={cand['score']:.3f} | {cand.get('title', '')[:45]}")

        if not detail_url.startswith("http"):
            continue

        tab_d = await browser.get(detail_url)
        await tab_d.sleep(5)

        video_urls = await extract_video_urls(tab_d)
        log(f"      영상: {len(video_urls)}개")

        if not video_urls:
            log(f"      → 영상 없음, 건너뜀")
            continue

        # 영상 다운로드 시도
        for vurl in video_urls[:3]:
            filepath = os.path.join(OUTPUT_DIR, f"{filepath_prefix}_video.mp4")
            log(f"      다운로드: {vurl[:60]}...")
            size = await download_video(vurl, filepath, detail_url)
            if size:
                log(f"      저장 완료! ({size}MB)")
                return {
                    "source": source_name,
                    "product": cand,
                    "video_url": vurl,
                    "video_file": filepath,
                    "size_mb": size
                }

        log(f"      → 다운로드 실패, 건너뜀")

    return None


async def run():
    import zendriver as zd

    print("=" * 70)
    print("  E2E 소싱: 쿠팡 → 영상 있는 상품 2개 찾기")
    print("  시각:", time.strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 70)

    browser = await zd.start(headless=False, browser_args=["--window-size=1400,900"])

    # ================================================================
    # STEP 1: 쿠팡 상품 정보 추출
    # ================================================================
    print("\n" + "=" * 70)
    print("STEP 1: 쿠팡 상품 정보 추출")
    print("=" * 70)

    search_url = "https://www.coupang.com/np/search?component=&q=" + urllib.parse.quote("무선 핸디 청소기") + "&channel=user"
    log(f"검색: {search_url}")
    tab = await browser.get(search_url)
    await tab.sleep(6)

    product_url = await tab.evaluate("""
        (() => {
            const links = document.querySelectorAll('a[href*="/vp/products/"]');
            for (const a of links) {
                if (a.href && a.href.includes('/vp/products/')) return a.href.split('?')[0];
            }
            return null;
        })()
    """)

    if not product_url:
        log("검색 결과에서 상품 URL을 찾을 수 없음")
        await browser.stop()
        return

    log(f"상품 URL: {product_url}")
    tab2 = await browser.get(product_url)
    await tab2.sleep(6)

    coupang_data = await tab2.evaluate("""
        (() => {
            const h1 = document.querySelector('h1.prod-buy-header__title, h2.prod-buy-header__title, .prod-buy-header__title');
            const ogTitle = document.querySelector('meta[property="og:title"]');
            const ogImage = document.querySelector('meta[property="og:image"]');
            const price = document.querySelector('.total-price strong');
            return {
                name: h1 ? h1.textContent.trim() : (ogTitle ? ogTitle.content.replace(/ \\| 쿠팡$/, '') : null),
                image: ogImage ? ogImage.content : null,
                price: price ? price.textContent.trim() : null,
                url: window.location.href
            };
        })()
    """)

    coupang_name = re.sub(r'\s*\|\s*쿠팡\s*$', '', ((coupang_data or {}).get("name") or "")).strip()
    coupang_image = (coupang_data or {}).get("image") or ""
    coupang_price = (coupang_data or {}).get("price") or ""

    log(f"상품명: {coupang_name}")
    log(f"가격: {coupang_price or '(추출 실패)'}")

    if not coupang_name or len(coupang_name) < 3:
        log("상품명 추출 실패, 중단")
        await browser.stop()
        return

    # ================================================================
    # STEP 2: 키워드 변환
    # ================================================================
    print("\n" + "=" * 70)
    print("STEP 2: 키워드 변환")
    print("=" * 70)

    keyword_map = {
        "청소기": {"cn": "吸尘器", "en": "vacuum cleaner"},
        "무선": {"cn": "无线", "en": "wireless"},
        "핸디": {"cn": "手持式", "en": "handheld"},
        "미니": {"cn": "迷你", "en": "mini"},
        "차량용": {"cn": "车载", "en": "car"},
        "소형": {"cn": "小型", "en": "portable"},
        "충전": {"cn": "充电式", "en": "rechargeable"},
        "물걸레": {"cn": "拖把", "en": "mop"},
        "스틱": {"cn": "立式", "en": "stick"},
        "진공": {"cn": "真空", "en": "vacuum"},
        "로봇": {"cn": "机器人", "en": "robot"},
    }

    cn_parts, en_parts = [], []
    for kr, tr in keyword_map.items():
        if kr in coupang_name:
            if tr["cn"]: cn_parts.append(tr["cn"])
            if tr["en"]: en_parts.append(tr["en"])

    if not cn_parts:
        cn_parts = ["无线", "手持式", "吸尘器"]
    if not en_parts:
        en_parts = ["wireless", "handheld", "vacuum cleaner"]

    cn_keyword = " ".join(cn_parts)
    en_keyword = " ".join(en_parts)
    log(f"중국어: {cn_keyword}")
    log(f"영어: {en_keyword}")

    # ================================================================
    # STEP 3: 1688 검색 (로그인 필요 시 스킵)
    # ================================================================
    print("\n" + "=" * 70)
    print("STEP 3: 1688 검색")
    print("=" * 70)

    products_1688 = []
    url_1688 = f"https://s.1688.com/selloffer/offer_search.htm?keywords={urllib.parse.quote(cn_keyword)}"
    log(f"URL: {url_1688}")
    tab_1688 = await browser.get(url_1688)
    await tab_1688.sleep(5)

    current_url = await tab_1688.evaluate("window.location.href") or ""
    if "login.taobao.com" in current_url or "login.1688.com" in current_url:
        log("1688 로그인 필요 → 스킵, AliExpress에서 2개로 폴백")
    else:
        # 스크롤
        await tab_1688.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        await tab_1688.sleep(2)
        await tab_1688.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await tab_1688.sleep(2)

        products_1688 = await tab_1688.evaluate("""
            (() => {
                const results = [];
                const processedIds = new Set();
                document.querySelectorAll('a[href*="detail.1688.com"], a[href*="offer/"], a[href*="offerId"]').forEach(a => {
                    if (results.length >= 30) return;
                    const href = a.href || '';
                    let offerId = null;
                    let m = href.match(/offer\\/(\\d{10,})/);
                    if (m) offerId = m[1];
                    if (!offerId) { m = href.match(/offerId[=:](\\d{10,})/); if (m) offerId = m[1]; }
                    if (!offerId || processedIds.has(offerId)) return;
                    processedIds.add(offerId);
                    const container = a.closest('[class*="item"], [class*="card"], [class*="offer"], li, div') || a.parentElement;
                    const img = container ? container.querySelector('img[src]') : null;
                    const titleEl = container ? (container.querySelector('[class*="title"], h4, h3, h2') || a) : a;
                    const title = (titleEl.title || titleEl.textContent || '').trim();
                    const priceEl = container ? container.querySelector('[class*="price"]') : null;
                    results.push({
                        id: offerId,
                        title: title.substring(0, 120),
                        price: priceEl ? priceEl.textContent.trim() : null,
                        image: img ? img.src : null,
                        url: 'https://detail.1688.com/offer/' + offerId + '.html'
                    });
                });
                return results;
            })()
        """) or []

    log(f"1688: {len(products_1688)}개 상품 수집")

    # ================================================================
    # STEP 4: AliExpress 검색
    # ================================================================
    print("\n" + "=" * 70)
    print("STEP 4: AliExpress 검색")
    print("=" * 70)

    url_ali = f"https://www.aliexpress.com/wholesale?SearchText={urllib.parse.quote(en_keyword)}"
    log(f"URL: {url_ali}")
    tab_ali = await browser.get(url_ali)
    await tab_ali.sleep(7)

    products_ali = await tab_ali.evaluate("""
        (() => {
            const seen = new Set();
            const items = [];
            document.querySelectorAll('a[href*="/item/"]').forEach(a => {
                if (items.length >= 20) return;
                const match = a.href.match(/item\\/(\\d+)/);
                if (!match || seen.has(match[1])) return;
                seen.add(match[1]);
                const card = a.closest('[class*="card"], [class*="Card"], [class*="product"], [class*="snippet"]') || a.parentElement;
                const img = card ? card.querySelector('img') : null;
                const priceEl = card ? card.querySelector('[class*="price"], [class*="Price"]') : null;
                const titleEl = card ? (card.querySelector('h1, h2, h3, [class*="title"], [class*="Title"]') || a) : a;
                items.push({
                    id: match[1],
                    title: titleEl ? titleEl.textContent.trim().substring(0, 100) : null,
                    price: priceEl ? priceEl.textContent.trim() : null,
                    image: img ? img.src : null,
                    url: 'https://ko.aliexpress.com/item/' + match[1] + '.html'
                });
            });
            return items;
        })()
    """) or []

    log(f"AliExpress: {len(products_ali)}개 상품 수집")
    for i, p in enumerate(products_ali[:3]):
        log(f"  [{i+1}] {(p.get('title') or 'N/A')[:50]}")

    # ================================================================
    # STEP 5: 유사도 정렬 → 영상 있는 상품 찾기
    # ================================================================
    print("\n" + "=" * 70)
    print("STEP 5: 영상 있는 상품 탐색")
    print("=" * 70)

    # 유사도 계산
    candidates_1688 = sorted(
        [{**p, "score": max(similarity_score(coupang_name, p.get("title", "")),
                           similarity_score(cn_keyword, p.get("title", ""))),
          "source": "1688"} for p in products_1688],
        key=lambda x: x["score"], reverse=True
    )

    candidates_ali = sorted(
        [{**p, "score": max(similarity_score(coupang_name, p.get("title", "")),
                           similarity_score(en_keyword, p.get("title", ""))),
          "source": "aliexpress"} for p in products_ali],
        key=lambda x: x["score"], reverse=True
    )

    # 목표: 총 2개 (1688 있으면 각 1개씩, 없으면 AliExpress 2개)
    need_from_ali = 2 if len(candidates_1688) == 0 else 1
    need_from_1688 = 2 - need_from_ali

    log(f"1688 후보: {len(candidates_1688)}개, AliExpress 후보: {len(candidates_ali)}개")
    log(f"목표: 1688 {need_from_1688}개 + AliExpress {need_from_ali}개")

    final_picks = []

    # 1688에서 찾기
    if need_from_1688 > 0 and candidates_1688:
        print(f"\n  --- 1688 영상 탐색 ---")
        pick = await find_product_with_video(browser, candidates_1688, "1688", "sourcing_1688")
        if pick:
            final_picks.append(pick)
        else:
            log("  1688: 영상 있는 상품 없음 → AliExpress에서 추가 탐색")
            need_from_ali += 1

    # AliExpress에서 찾기
    print(f"\n  --- AliExpress 영상 탐색 ({need_from_ali}개 목표) ---")
    ali_found = 0
    ali_idx = 0
    for cand in candidates_ali[:15]:
        if ali_found >= need_from_ali:
            break
        ali_idx += 1
        detail_url = cand.get("url", "")
        log(f"  [{ali_idx}] score={cand['score']:.3f} | {cand.get('title', '')[:45]}")

        if not detail_url.startswith("http"):
            continue

        tab_d = await browser.get(detail_url)
        await tab_d.sleep(5)

        video_urls = await extract_video_urls(tab_d)
        log(f"      영상: {len(video_urls)}개")

        if not video_urls:
            log(f"      → 영상 없음, 건너뜀")
            continue

        for vurl in video_urls[:3]:
            filepath = os.path.join(OUTPUT_DIR, f"sourcing_aliexpress_{ali_found+1}_video.mp4")
            log(f"      다운로드: {vurl[:60]}...")
            size = await download_video(vurl, filepath, detail_url)
            if size:
                log(f"      저장 완료! ({size}MB)")
                final_picks.append({
                    "source": "aliexpress",
                    "product": cand,
                    "video_url": vurl,
                    "video_file": filepath,
                    "size_mb": size
                })
                ali_found += 1
                break
        else:
            log(f"      → 다운로드 실패, 건너뜀")

    await browser.stop()

    # ================================================================
    # 최종 보고서
    # ================================================================
    print("\n\n" + "=" * 70)
    print("  최종 결과")
    print("=" * 70)

    print(f"\n  [원본 쿠팡 상품]")
    print(f"    상품명: {coupang_name}")
    print(f"    가격: {coupang_price or '(미추출)'}")
    print(f"    링크: {product_url}")

    print(f"\n  [소싱 결과: 영상 있는 상품 {len(final_picks)}개]")
    for i, pick in enumerate(final_picks):
        p = pick["product"]
        print(f"\n    [{i+1}] ({pick['source'].upper()}) 유사도: {p['score']:.3f}")
        print(f"        제목: {p.get('title', 'N/A')[:60]}")
        print(f"        링크: {p.get('url', 'N/A')}")
        print(f"        영상: {pick['video_file']}")
        print(f"        크기: {pick['size_mb']}MB")

    if not final_picks:
        print("    영상 있는 상품을 찾지 못했습니다.")

    # JSON 보고서
    report = {
        "original_coupang": {
            "name": coupang_name,
            "price": coupang_price,
            "url": product_url,
            "image": coupang_image
        },
        "search_keywords": {"chinese": cn_keyword, "english": en_keyword},
        "sourcing_results": [
            {
                "rank": i + 1,
                "source": pick["source"],
                "similarity": pick["product"]["score"],
                "title": pick["product"].get("title"),
                "price": pick["product"].get("price"),
                "url": pick["product"].get("url"),
                "image": pick["product"].get("image"),
                "video_url": pick["video_url"],
                "video_file": pick["video_file"],
                "video_size_mb": pick["size_mb"]
            }
            for i, pick in enumerate(final_picks)
        ],
        "stats": {
            "1688_candidates": len(candidates_1688),
            "aliexpress_candidates": len(candidates_ali),
            "videos_found": len(final_picks)
        }
    }

    report_path = os.path.join(OUTPUT_DIR, "sourcing_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n  보고서: {report_path}")


if __name__ == "__main__":
    asyncio.run(run())
