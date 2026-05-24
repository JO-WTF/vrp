import math
from datetime import datetime, timedelta

def parse_solomon(content: str):
    lines = content.strip().split('\n')
    name = lines[0].strip()
    
    idx = 0
    while idx < len(lines) and not lines[idx].strip().startswith("VEHICLE"):
        idx += 1
    idx += 2
    parts = lines[idx].split()
    vehicle_count = int(parts[0])
    capacity = int(parts[1])
    
    while idx < len(lines) and not lines[idx].strip().startswith("CUSTOMER"):
        idx += 1
    idx += 3 
    
    customers = []
    for line in lines[idx:]:
        if not line.strip(): continue
        p = line.split()
        customers.append({
            "id": int(p[0]),
            "x": float(p[1]),
            "y": float(p[2]),
            "demand": int(p[3]),
            "ready": float(p[4]),
            "due": float(p[5]),
            "service": float(p[6])
        })
        
    customers.sort(key=lambda c: c["id"])
    depot = next(c for c in customers if c["id"] == 0)
    jobs = [c for c in customers if c["id"] != 0]
    
    # Map coordinates to Beijing bounding box
    min_x = min(c["x"] for c in customers)
    max_x = max(c["x"] for c in customers)
    min_y = min(c["y"] for c in customers)
    max_y = max(c["y"] for c in customers)
    range_x = max_x - min_x if max_x > min_x else 1
    range_y = max_y - min_y if max_y > min_y else 1
    min_lng, max_lng = 116.30, 116.45
    min_lat, max_lat = 39.85, 40.00
    for c in customers:
        c["lng"] = min_lng + ((c["x"] - min_x) / range_x) * (max_lng - min_lng)
        c["lat"] = min_lat + ((c["y"] - min_y) / range_y) * (max_lat - min_lat)
    
    points = [(c["x"], c["y"]) for c in customers]
    distances = []
    
    for i in range(len(points)):
        for j in range(len(points)):
            dx = points[i][0] - points[j][0]
            dy = points[i][1] - points[j][1]
            dist = math.sqrt(dx*dx + dy*dy)
            dist_int = int(round(dist * 10))
            distances.append(dist_int)
            
    matrix = {
        "profile": "normal_car",
        "distances": distances,
        "travelTimes": distances 
    }
    
    epoch = datetime(2023, 1, 1, 0, 0, 0)
    def fmt_time(t):
        return (epoch + timedelta(seconds=t * 10)).strftime("%Y-%m-%dT%H:%M:%SZ")

    pragmatic_jobs = []
    for j in jobs:
        pragmatic_jobs.append({
            "id": f"job_{j['id']}",
            "deliveries": [{
                "places": [{
                    "location": {"lat": j["lat"], "lng": j["lng"]},
                    "duration": j["service"] * 10,
                    "times": [[fmt_time(j['ready']), fmt_time(j['due'])]]
                }],
                "demand": [j["demand"]]
            }]
        })
        
    problem = {
        "plan": {
            "jobs": pragmatic_jobs
        },
        "fleet": {
            "vehicles": [{
                "typeId": "vehicle",
                "vehicleIds": [f"v_{i+1}" for i in range(vehicle_count)],
                "profile": {"matrix": "normal_car"},
                "costs": {"fixed": 0.0, "distance": 1.0, "time": 0.0},
                "shifts": [{
                    "start": {
                        "earliest": fmt_time(depot['ready']),
                        "location": {"lat": depot["lat"], "lng": depot["lng"]}
                    },
                    "end": {
                        "latest": fmt_time(depot['due']),
                        "location": {"lat": depot["lat"], "lng": depot["lng"]}
                    }
                }],
                "capacity": [capacity]
            }],
            "profiles": [{"name": "normal_car"}]
        }
    }
    
    return name, problem, matrix
