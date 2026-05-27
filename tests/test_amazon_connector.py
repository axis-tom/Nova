"""
Amazon PAAPI 连接器测试脚本
运行方式: cd Nova-refactor-architecture-ts && python -m pytest tests/test_amazon_connector.py -v
或直接运行: cd Nova-refactor-architecture-ts && python tests/test_amazon_connector.py
"""
import os
import sys
import json
import asyncio
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置测试环境变量
os.environ.setdefault("AMAZON_ACCESS_KEY", "test_access_key")
os.environ.setdefault("AMAZON_SECRET_KEY", "test_secret_key")
os.environ.setdefault("AMAZON_ASSOCIATE_TAG", "test_tag")
os.environ.setdefault("AMAZON_MARKETPLACE", "www.amazon.com")


def print_separator(title: str):
    """打印分隔线"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


async def test_aws_signature():
    """测试 AWS Signature V4 签名生成"""
    print_separator("测试 AWS Signature V4 签名")

    from backend.connectors.amazon.client import AmazonPAAPIClient

    client = AmazonPAAPIClient(
        access_key="AKIAIOSFODNN7EXAMPLE",
        secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        associate_tag="test-20",
        marketplace="www.amazon.com",
    )

    # 测试签名生成
    payload = {
        "Keywords": "test",
        "PartnerTag": "test-20",
        "PartnerType": "Associates",
        "Marketplace": "www.amazon.com",
    }

    headers, body = client._build_signed_request("searchitems", payload)

    print(f"✓ 签名头生成成功")
    print(f"  Authorization: {headers.get('Authorization', '')[:80]}...")
    print(f"  X-Amz-Date: {headers.get('X-Amz-Date', '')}")
    print(f"  X-Amz-Target: {headers.get('X-Amz-Target', '')}")
    print(f"  Content-Encoding: {headers.get('Content-Encoding', '')}")
    print(f"  Body 长度: {len(body)} 字节")

    # 验证签名头包含必要字段
    auth_header = headers.get("Authorization", "")
    assert "AWS4-HMAC-SHA256" in auth_header, "缺少算法标识"
    assert "Credential=" in auth_header, "缺少 Credential"
    assert "SignedHeaders=" in auth_header, "缺少 SignedHeaders"
    assert "Signature=" in auth_header, "缺少 Signature"
    print("✓ 签名头格式验证通过")

    # 验证必填头
    assert "Host" in headers, "缺少 Host 头"
    assert "X-Amz-Date" in headers, "缺少 X-Amz-Date 头"
    assert "X-Amz-Target" in headers, "缺少 X-Amz-Target 头"
    assert "Authorization" in headers, "缺少 Authorization 头"
    print("✓ 必填请求头验证通过")

    return True


async def test_models():
    """测试数据模型"""
    print_separator("测试数据模型")

    from backend.connectors.amazon.models import (
        AmazonProduct, AmazonSearchResult, AmazonPrice, AmazonRating,
        AmazonReview, AmazonPriceHistory, AmazonCompetitor
    )

    # 测试 AmazonPrice
    price = AmazonPrice(amount=29.99, currency="USD", display_amount="$29.99")
    assert price.amount == 29.99
    assert price.currency == "USD"
    assert price.display_amount == "$29.99"
    print(f"✓ AmazonPrice: {price.display_amount}")

    # 测试 AmazonRating
    rating = AmazonRating(overall_rating=4.5, total_reviews=100)
    assert rating.overall_rating == 4.5
    assert rating.total_reviews == 100
    print(f"✓ AmazonRating: {rating.overall_rating}/5 ({rating.total_reviews} reviews)")

    # 测试 AmazonProduct
    product = AmazonProduct(
        asin="B0EXAMPLE123",
        title="Test Product",
        url="https://www.amazon.com/dp/B0EXAMPLE123",
        price=price,
        rating=rating,
    )
    assert product.asin == "B0EXAMPLE123"
    assert product.title == "Test Product"
    assert product.price.amount == 29.99
    print(f"✓ AmazonProduct: {product.title} ({product.asin})")

    # 测试 AmazonSearchResult
    search_result = AmazonSearchResult(
        total_results=1,
        products=[product],
    )
    assert search_result.total_results == 1
    assert len(search_result.products) == 1
    print(f"✓ AmazonSearchResult: {search_result.total_results} results")

    # 测试 AmazonReview
    review = AmazonReview(
        asin="B0EXAMPLE123",
        rating=rating,
        review_summary="Test summary",
    )
    assert review.asin == "B0EXAMPLE123"
    assert review.review_summary == "Test summary"
    print(f"✓ AmazonReview: {review.asin}")

    # 测试 AmazonPriceHistory
    price_history = AmazonPriceHistory(
        asin="B0EXAMPLE123",
        current_price=price,
        price_trend="stable",
    )
    assert price_history.asin == "B0EXAMPLE123"
    assert price_history.price_trend == "stable"
    print(f"✓ AmazonPriceHistory: {price_history.asin} ({price_history.price_trend})")

    # 测试 AmazonCompetitor
    competitor = AmazonCompetitor(
        asin="B0EXAMPLE456",
        title="Competitor Product",
        price=AmazonPrice(amount=24.99, currency="USD"),
    )
    assert competitor.asin == "B0EXAMPLE456"
    assert competitor.price.amount == 24.99
    print(f"✓ AmazonCompetitor: {competitor.title} (${competitor.price.amount})")

    return True


async def test_parse_search_result():
    """测试搜索结果解析"""
    print_separator("测试搜索结果解析")

    from backend.connectors.amazon.client import AmazonPAAPIClient
    from backend.connectors.amazon.product_search import AmazonProductSearch

    client = AmazonPAAPIClient(
        access_key="test",
        secret_key="test",
        associate_tag="test-20",
    )
    searcher = AmazonProductSearch(client)

    # 模拟 PAAPI 响应
    mock_response = {
        "SearchResult": {
            "TotalResultCount": 2,
            "TotalPages": 1,
            "Items": [
                {
                    "ASIN": "B0EXAMPLE001",
                    "ItemInfo": {
                        "Title": {"Value": "Test Product 1"},
                        "Features": {"DisplayValues": ["Feature 1", "Feature 2"]},
                        "ByLineInfo": {
                            "Brand": {"Value": "TestBrand"},
                            "Manufacturer": {"Value": "TestMfg"},
                        },
                        "ProductInfo": {
                            "Dimensions": {"Height": "10", "Width": "5", "Length": "3", "Unit": "inches"},
                            "ItemWeight": {"Value": "1.5", "Unit": "pounds"},
                        },
                        "Classifications": {"Binding": {"Value": "Electronics"}},
                    },
                    "Offers": {
                        "Listings": [
                            {
                                "Price": {"Amount": 49.99, "Currency": "USD", "DisplayAmount": "$49.99"},
                                "SavingBasis": {"Amount": 10.00, "Percentage": 20},
                                "IsPrimeExclusive": True,
                                "Availability": {"Message": "In Stock"},
                            }
                        ],
                        "Summaries": [
                            {"HighestPrice": {"Amount": 59.99}, "LowestPrice": {"Amount": 39.99}}
                        ],
                    },
                    "Images": {
                        "Primary": {
                            "Medium": {"URL": "https://example.com/img.jpg"},
                            "Large": {"URL": "https://example.com/img_large.jpg"},
                        }
                    },
                    "BrowseNodeInfo": {
                        "BrowseNodes": [
                            {
                                "Id": "123",
                                "DisplayName": "Electronics",
                                "Ancestor": {
                                    "Id": "0",
                                    "DisplayName": "All",
                                }
                            }
                        ],
                        "WebsiteSalesRank": {"Value": 500, "DisplayName": "Electronics"},
                    },
                    "CustomerReviews": {
                        "StarRating": {"Value": 4.5},
                        "Count": 100,
                    },
                },
                {
                    "ASIN": "B0EXAMPLE002",
                    "ItemInfo": {
                        "Title": {"Value": "Test Product 2"},
                        "Features": {"DisplayValues": ["Feature A"]},
                        "ByLineInfo": {
                            "Brand": {"Value": "AnotherBrand"},
                        },
                        "Classifications": {"Binding": {"Value": "Books"}},
                    },
                    "Offers": {
                        "Listings": [
                            {
                                "Price": {"Amount": 19.99, "Currency": "USD", "DisplayAmount": "$19.99"},
                                "IsPrimeExclusive": False,
                            }
                        ],
                    },
                    "Images": {
                        "Primary": {
                            "Medium": {"URL": "https://example.com/img2.jpg"},
                        }
                    },
                    "BrowseNodeInfo": {
                        "BrowseNodes": [{"Id": "456", "DisplayName": "Books"}],
                    },
                    "CustomerReviews": {
                        "StarRating": {"Value": 4.0},
                        "Count": 50,
                    },
                },
            ]
        }
    }

    result = searcher._parse_search_result(mock_response, "test products")

    assert result.total_results == 2
    assert len(result.products) == 2
    assert result.products[0].asin == "B0EXAMPLE001"
    assert result.products[0].title == "Test Product 1"
    assert result.products[0].price.amount == 49.99
    assert result.products[0].price.is_prime == True
    assert result.products[0].rating.overall_rating == 4.5
    assert result.products[0].rating.total_reviews == 100
    assert result.products[0].brand == "TestBrand"
    assert result.products[0].category == "Electronics"
    assert len(result.products[0].feature_bullets) == 2
    assert result.products[0].availability == "In Stock"

    assert result.products[1].asin == "B0EXAMPLE002"
    assert result.products[1].title == "Test Product 2"
    assert result.products[1].price.amount == 19.99
    assert result.products[1].rating.overall_rating == 4.0

    print(f"✓ 解析了 {len(result.products)} 个商品")
    print(f"  商品1: {result.products[0].title} - ${result.products[0].price.amount}")
    print(f"  商品2: {result.products[1].title} - ${result.products[1].price.amount}")
    print(f"  评分: {result.products[0].rating.overall_rating}/5 ({result.products[0].rating.total_reviews} reviews)")
    print(f"  BSR: #{result.products[0].bsr.rank} in {result.products[0].bsr.category}")

    return True


async def test_review_analyzer():
    """测试评论分析器"""
    print_separator("测试评论分析器")

    from backend.connectors.amazon.client import AmazonPAAPIClient
    from backend.connectors.amazon.review_analyzer import AmazonReviewAnalyzer
    from backend.connectors.amazon.models import AmazonRating

    client = AmazonPAAPIClient(
        access_key="test",
        secret_key="test",
        associate_tag="test-20",
    )
    analyzer = AmazonReviewAnalyzer(client)

    # 测试摘要生成
    rating = AmazonRating(overall_rating=4.5, total_reviews=100)
    summary = analyzer._generate_summary(rating, "Test Product")
    assert "Test Product" in summary
    assert "100" in summary
    assert "4.5" in summary
    print(f"✓ 评论摘要: {summary}")

    # 测试低评分摘要
    low_rating = AmazonRating(overall_rating=2.0, total_reviews=10)
    low_summary = analyzer._generate_summary(low_rating, "Bad Product")
    assert "差评" in low_summary
    print(f"✓ 低评分摘要: {low_summary}")

    # 测试评论洞察丰富
    review = analyzer._enrich_review_insights(
        type('obj', (object,), {
            "asin": "B0TEST",
            "rating": AmazonRating(overall_rating=4.5, total_reviews=100),
            "sentiment_positive_pct": 0.0,
            "sentiment_negative_pct": 0.0,
            "sentiment_neutral_pct": 0.0,
            "common_praise": [],
            "common_complaints": [],
            "customer_needs": [],
        })(),
        AmazonRating(overall_rating=4.5, total_reviews=100),
    )

    assert review.sentiment_positive_pct > 0
    assert len(review.common_praise) > 0
    print(f"✓ 评论洞察: 正面 {review.sentiment_positive_pct}%, 负面 {review.sentiment_negative_pct}%")
    print(f"  常见好评: {review.common_praise[:2]}")

    return True


async def test_price_tracker():
    """测试价格追踪器"""
    print_separator("测试价格追踪器")

    from backend.connectors.amazon.client import AmazonPAAPIClient
    from backend.connectors.amazon.price_tracker import AmazonPriceTracker

    client = AmazonPAAPIClient(
        access_key="test",
        secret_key="test",
        associate_tag="test-20",
    )
    tracker = AmazonPriceTracker(client)

    # 测试价格历史记录
    tracker._price_history["B0TEST"] = [
        {"price": 100.0, "timestamp": "2026-05-01T00:00:00"},
        {"price": 95.0, "timestamp": "2026-05-05T00:00:00"},
        {"price": 90.0, "timestamp": "2026-05-10T00:00:00"},
    ]

    history = tracker.get_price_history("B0TEST")
    assert len(history) == 3
    assert history[0]["price"] == 100.0
    assert history[-1]["price"] == 90.0
    print(f"✓ 价格历史: {len(history)} 条记录")
    print(f"  最新价格: ${history[-1]['price']}")

    # 测试清空历史
    tracker.clear_price_history("B0TEST")
    assert len(tracker.get_price_history("B0TEST")) == 0
    print("✓ 价格历史清空成功")

    # 测试批量清空
    tracker._price_history["B0TEST1"] = [{"price": 50.0, "timestamp": "2026-05-01T00:00:00"}]
    tracker._price_history["B0TEST2"] = [{"price": 75.0, "timestamp": "2026-05-01T00:00:00"}]
    tracker.clear_price_history()
    assert len(tracker._price_history) == 0
    print("✓ 全部价格历史清空成功")

    return True


async def test_data_source_registration():
    """测试数据源注册"""
    print_separator("测试数据源注册")

    from backend.config.data_source_providers import DATA_SOURCE_TYPES

    assert "amazon" in DATA_SOURCE_TYPES, "Amazon 数据源未注册"
    amazon_def = DATA_SOURCE_TYPES["amazon"]

    assert amazon_def.type == "amazon"
    assert amazon_def.name == "Amazon 商品数据"
    print(f"✓ Amazon 数据源已注册: {amazon_def.name}")

    # 验证配置字段
    field_names = [f.name for f in amazon_def.fields]
    assert "access_key" in field_names, "缺少 access_key 字段"
    assert "secret_key" in field_names, "缺少 secret_key 字段"
    assert "associate_tag" in field_names, "缺少 associate_tag 字段"
    assert "marketplace" in field_names, "缺少 marketplace 字段"
    print(f"✓ 配置字段: {', '.join(field_names)}")

    # 验证站点选项
    marketplace_field = next(f for f in amazon_def.fields if f.name == "marketplace")
    assert marketplace_field.options is not None
    assert len(marketplace_field.options) >= 20
    print(f"✓ 支持 {len(marketplace_field.options)} 个站点")

    return True


async def test_env_config():
    """测试环境变量配置"""
    print_separator("测试环境变量配置")

    from backend.connectors.amazon.client import AmazonPAAPIClient

    # 测试从环境变量创建客户端
    client = AmazonPAAPIClient(
        access_key=os.environ.get("AMAZON_ACCESS_KEY", ""),
        secret_key=os.environ.get("AMAZON_SECRET_KEY", ""),
        associate_tag=os.environ.get("AMAZON_ASSOCIATE_TAG", ""),
        marketplace=os.environ.get("AMAZON_MARKETPLACE", "www.amazon.com"),
    )

    assert client.access_key == "test_access_key"
    assert client.secret_key == "test_secret_key"
    assert client.associate_tag == "test_tag"
    assert client.marketplace == "www.amazon.com"
    assert client.region == "us-east-1"
    assert client.endpoint == "webservices.amazon.com"

    print(f"✓ 环境变量配置读取成功")
    print(f"  Marketplace: {client.marketplace}")
    print(f"  Region: {client.region}")
    print(f"  Endpoint: {client.endpoint}")

    return True


async def test_marketplace_config():
    """测试多站点配置"""
    print_separator("测试多站点配置")

    from backend.connectors.amazon.client import AmazonPAAPIClient, REGION_MAP, PAAPI_ENDPOINTS

    # 测试日本站点
    jp_client = AmazonPAAPIClient(
        access_key="test", secret_key="test",
        associate_tag="test-22", marketplace="www.amazon.co.jp",
    )
    assert jp_client.region == "us-west-2"
    assert jp_client.endpoint == "webservices.amazon.co.jp"
    print(f"✓ 日本站点: {jp_client.marketplace} -> {jp_client.region}")

    # 测试德国站点
    de_client = AmazonPAAPIClient(
        access_key="test", secret_key="test",
        associate_tag="test-21", marketplace="www.amazon.de",
    )
    assert de_client.region == "eu-west-1"
    assert de_client.endpoint == "webservices.amazon.de"
    print(f"✓ 德国站点: {de_client.marketplace} -> {de_client.region}")

    # 测试英国站点
    uk_client = AmazonPAAPIClient(
        access_key="test", secret_key="test",
        associate_tag="test-21", marketplace="www.amazon.co.uk",
    )
    assert uk_client.region == "eu-west-1"
    assert uk_client.endpoint == "webservices.amazon.co.uk"
    print(f"✓ 英国站点: {uk_client.marketplace} -> {uk_client.region}")

    # 验证所有站点都有映射
    print(f"\n✓ 共支持 {len(PAAPI_ENDPOINTS)} 个站点:")
    for marketplace, endpoint in list(PAAPI_ENDPOINTS.items())[:5]:
        region = REGION_MAP.get(marketplace, "unknown")
        print(f"  {marketplace:25s} -> {endpoint:30s} ({region})")
    print(f"  ... 及其他 {len(PAAPI_ENDPOINTS) - 5} 个站点")

    return True


async def main():
    """运行所有测试"""
    print(f"\n{'#'*60}")
    print(f"#  Amazon PAAPI 连接器测试套件")
    print(f"#  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}")

    tests = [
        ("AWS Signature V4 签名", test_aws_signature),
        ("数据模型", test_models),
        ("搜索结果解析", test_parse_search_result),
        ("评论分析器", test_review_analyzer),
        ("价格追踪器", test_price_tracker),
        ("数据源注册", test_data_source_registration),
        ("环境变量配置", test_env_config),
        ("多站点配置", test_marketplace_config),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            await test_func()
            print(f"\n  ✅ {name} 测试通过")
            passed += 1
        except Exception as e:
            print(f"\n  ❌ {name} 测试失败: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    # 打印总结
    print(f"\n{'='*60}")
    print(f"  测试完成: {passed} 通过, {failed} 失败, {passed + failed} 总计")
    print(f"{'='*60}")

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)