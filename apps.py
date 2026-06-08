"""
tests.py — Django test suite for Bluestock Fintech
Run: pytest django_app/companies/tests.py -v --tb=short
Or:  cd django_app && python manage.py test companies
"""

import json
from django.test import TestCase, Client


class DataServiceTests(TestCase):

    def test_get_all_companies_returns_list(self):
        from companies.data_service import get_all_companies
        result = get_all_companies()
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_every_company_has_required_fields(self):
        from companies.data_service import get_all_companies
        required = ["symbol","company_name","sector","health_score","health_label"]
        for company in get_all_companies():
            for field in required:
                self.assertIn(field, company)

    def test_health_score_valid_range(self):
        from companies.data_service import get_all_companies
        for c in get_all_companies():
            self.assertGreaterEqual(c["health_score"], 0)
            self.assertLessEqual(c["health_score"], 100)

    def test_health_label_valid(self):
        from companies.data_service import get_all_companies
        valid = {"EXCELLENT","GOOD","AVERAGE","WEAK","POOR"}
        for c in get_all_companies():
            self.assertIn(c["health_label"], valid)

    def test_get_company_tcs(self):
        from companies.data_service import get_company
        tcs = get_company("TCS")
        self.assertIsNotNone(tcs)
        self.assertEqual(tcs["symbol"], "TCS")

    def test_get_company_invalid_none(self):
        from companies.data_service import get_company
        self.assertIsNone(get_company("NOTACOMPANY"))

    def test_chart_data_keys(self):
        from companies.data_service import get_chart_data
        data = get_chart_data("TCS")
        for key in ["years","sales","net_profit","opm","cf_years","operating","health_score"]:
            self.assertIn(key, data)

    def test_chart_data_consistent_lengths(self):
        from companies.data_service import get_chart_data
        data = get_chart_data("TCS")
        n = len(data["years"])
        self.assertEqual(len(data["sales"]), n)
        self.assertEqual(len(data["net_profit"]), n)

    def test_screener_label_filter(self):
        from companies.data_service import get_screener_results
        results = get_screener_results({"label": "EXCELLENT"})
        for r in results:
            self.assertEqual(r["health_label"], "EXCELLENT")

    def test_search_tcs(self):
        from companies.data_service import search_companies
        results = search_companies("TCS")
        self.assertIn("TCS", [r["symbol"] for r in results])


class PageTests(TestCase):

    def setUp(self):
        self.client = Client()

    def test_home(self):
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_company_list(self):
        self.assertEqual(self.client.get("/companies/").status_code, 200)

    def test_company_tcs(self):
        self.assertEqual(self.client.get("/company/TCS/").status_code, 200)

    def test_company_invalid_404(self):
        self.assertEqual(self.client.get("/company/NOTREAL/").status_code, 404)

    def test_compare(self):
        self.assertEqual(self.client.get("/compare/").status_code, 200)

    def test_screener(self):
        self.assertEqual(self.client.get("/screener/").status_code, 200)

    def test_sector_it(self):
        self.assertEqual(self.client.get("/sector/IT/").status_code, 200)


class APITests(TestCase):

    def setUp(self):
        self.client = Client()

    def test_api_charts_200(self):
        self.assertEqual(self.client.get("/api/charts/TCS/").status_code, 200)

    def test_api_charts_json(self):
        r = self.client.get("/api/charts/TCS/")
        data = json.loads(r.content)
        self.assertIn("years", data)
        self.assertIn("sales", data)

    def test_api_companies_list(self):
        r = self.client.get("/api/companies/")
        data = json.loads(r.content)
        self.assertIn("results", data)
        self.assertIsInstance(data["results"], list)

    def test_api_screener_filter(self):
        r = self.client.get("/api/screener/?label=EXCELLENT")
        data = json.loads(r.content)
        for item in data["results"]:
            self.assertEqual(item["health_label"], "EXCELLENT")

    def test_api_post_not_allowed(self):
        self.assertEqual(self.client.post("/api/charts/TCS/").status_code, 405)
