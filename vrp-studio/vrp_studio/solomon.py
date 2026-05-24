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
    
    points = [(c["x"], c["y"]) for c in customers]
    distances = []
    
    for i in range(len(points)):
        for j in range(len(points)):
            dx = points[i][0] - points[j][0]
            dy = points[i][1] - points[j][1]
            dist = round(math.sqrt(dx*dx + dy*dy), 2)
            distances.append(dist)
            
    matrix = {
        "profile": "normal_car",
        "distances": distances,
        "travelTimes": distances 
    }
    
    epoch = datetime(2023, 1, 1, 0, 0, 0)
    def fmt_time(t):
        return (epoch + timedelta(seconds=t)).strftime("%Y-%m-%dT%H:%M:%SZ")

    pragmatic_jobs = []
    for j in jobs:
        pragmatic_jobs.append({
            "id": f"job_{j['id']}",
            "deliveries": [{
                "places": [{
                    "location": {"index": j["id"]},
                    "duration": j["service"],
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
                        "location": {"index": 0}
                    },
                    "end": {
                        "latest": fmt_time(depot['due']),
                        "location": {"index": 0}
                    }
                }],
                "capacity": [capacity]
            }],
            "profiles": [{"name": "normal_car"}]
        }
    }
    
    return name, problem, matrix
