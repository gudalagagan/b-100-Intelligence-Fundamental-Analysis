import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from . import data_service as ds

def home(request):
    query = request.GET.get("q","").strip()
    search_results = ds.search_companies(query) if query else []
    all_co   = ds.get_all_companies()
    sectors  = ds.get_sectors()
    featured = all_co[:6]
    label_counts = {}
    for c in all_co:
        label_counts[c["health_label"]] = label_counts.get(c["health_label"],0)+1
    return render(request,"home.html",{
        "featured":featured,"sectors":sectors,
        "label_counts":label_counts,"query":query,
        "search_results":search_results,"total":len(all_co),
    })

def company_list(request):
    sector_filter = request.GET.get("sector","")
    label_filter  = request.GET.get("label","")
    sort_by       = request.GET.get("sort","health_score")
    all_co = ds.get_all_companies()
    if sector_filter:
        all_co = [c for c in all_co if c["sector"]==sector_filter]
    if label_filter:
        all_co = [c for c in all_co if c["health_label"]==label_filter]
    reverse = sort_by in ("health_score","roce","roe")
    all_co  = sorted(all_co, key=lambda x: x.get(sort_by) or 0, reverse=reverse)
    sectors = sorted({c["sector"] for c in ds.get_all_companies()})
    labels  = ["EXCELLENT","GOOD","AVERAGE","WEAK","POOR"]
    return render(request,"company_list.html",{
        "companies":all_co,"sectors":sectors,"labels":labels,
        "sector_filter":sector_filter,"label_filter":label_filter,
        "sort_by":sort_by,"total":len(all_co),
    })

def company_detail(request, symbol):
    company = ds.get_company(symbol.upper())
    if not company:
        return render(request,"404.html",status=404)
    chart_data = ds.get_chart_data(symbol.upper())
    return render(request,"company_detail.html",{
        "company":company,
        "chart_data_json": json.dumps(chart_data),
    })

def compare(request):
    symbols = request.GET.getlist("s")
    companies = []
    for s in symbols[:4]:
        c = ds.get_company(s.upper())
        if c:
            cd = ds.get_chart_data(s.upper())
            c["chart_data"] = cd
            companies.append(c)
    all_co = ds.get_all_companies()
    return render(request,"compare.html",{
        "companies":companies,
        "all_companies":all_co,
        "selected_symbols":symbols,
        "chart_data_json": json.dumps([ds.get_chart_data(s.upper()) for s in symbols[:4] if ds.get_company(s.upper())]),
        "labels_json": json.dumps([c["company_name"] for c in companies]),
    })

def screener(request):
    filters = {}
    for f in ["min_roe","max_de","min_opm","sector","label","min_score"]:
        v = request.GET.get(f,"").strip()
        if v:
            filters[f] = v
    results = ds.get_screener_results(filters) if filters else ds.get_all_companies()
    sectors = sorted({c["sector"] for c in ds.get_all_companies()})
    labels  = ["EXCELLENT","GOOD","AVERAGE","WEAK","POOR"]
    return render(request,"screener.html",{
        "results":results,"filters":filters,
        "sectors":sectors,"labels":labels,"total":len(results),
    })

def sector_detail(request, name):
    sector = ds.get_sector(name)
    if not sector:
        return render(request,"404.html",status=404)
    return render(request,"sector_detail.html",{"sector":sector})

# ── API endpoints ──────────────────────────────────────────────────────────
@require_GET
def api_company_charts(request, symbol):
    data = ds.get_chart_data(symbol.upper())
    return JsonResponse(data)

@require_GET
def api_companies(request):
    q = request.GET.get("q","")
    results = ds.search_companies(q) if q else ds.get_all_companies()
    return JsonResponse({"results":results})

@require_GET
def api_screener(request):
    filters = {k:v for k,v in request.GET.items() if v}
    return JsonResponse({"results": ds.get_screener_results(filters)})
