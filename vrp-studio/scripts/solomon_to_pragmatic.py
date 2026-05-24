import argparse
import json
import math
import os

def parse_solomon(file_path):
    with open(file_path, 'r') as f:
        lines = f.readlines()

    vehicle_count = 0
    vehicle_capacity = 0
    nodes = []

    # Simple state machine to parse solomon format
    state = "HEADER"
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if state == "HEADER":
            if line.startswith("VEHICLE"):
                state = "VEHICLE"
        elif state == "VEHICLE":
            if line.startswith("NUMBER"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                vehicle_count = int(parts[0])
                vehicle_capacity = int(parts[1])
                state = "CUSTOMER_HEADER"
        elif state == "CUSTOMER_HEADER":
            if line.startswith("CUST NO."):
                continue
            state = "CUSTOMER"
            # Attempt to parse first node if it's on this line (usually it's on the next)
            parts = line.split()
            if len(parts) >= 7 and parts[0].isdigit():
                _add_node(nodes, parts)
        elif state == "CUSTOMER":
            parts = line.split()
            if len(parts) >= 7 and parts[0].isdigit():
                _add_node(nodes, parts)

    return vehicle_count, vehicle_capacity, nodes

def _add_node(nodes, parts):
    nodes.append({
        "id": parts[0],
        "x": float(parts[1]),
        "y": float(parts[2]),
        "demand": int(parts[3]),
        # Scale times by 10 as well to match the distance/travelTime scaling
        "ready": float(parts[4]) * 10,
        "due": float(parts[5]) * 10,
        "service": float(parts[6]) * 10
    })

def map_coordinates(nodes, min_lng, min_lat, max_lng, max_lat):
    if not nodes:
        return
    
    min_x = min(n['x'] for n in nodes)
    max_x = max(n['x'] for n in nodes)
    min_y = min(n['y'] for n in nodes)
    max_y = max(n['y'] for n in nodes)

    range_x = max_x - min_x if max_x > min_x else 1
    range_y = max_y - min_y if max_y > min_y else 1
    
    range_lng = max_lng - min_lng
    range_lat = max_lat - min_lat

    for n in nodes:
        # Map X to Lng, Y to Lat
        norm_x = (n['x'] - min_x) / range_x
        norm_y = (n['y'] - min_y) / range_y
        
        n['lng'] = min_lng + norm_x * range_lng
        n['lat'] = min_lat + norm_y * range_lat

def build_pragmatic_problem(name, vehicle_count, vehicle_capacity, nodes):
    # Node 0 is the depot
    depot = nodes[0]
    jobs = []
    
    for n in nodes[1:]:
        job = {
            "id": f"job_{n['id']}",
            "pickups": [
                {
                    "places": [
                        {
                            "location": {
                                "lat": n['lat'],
                                "lng": n['lng']
                            },
                            "duration": n['service'],
                            "times": [
                                [n['ready'], n['due']]
                            ]
                        }
                    ],
                    "demand": [n['demand']]
                }
            ]
        }
        jobs.append(job)

    fleet = {
        "vehicles": [
            {
                "typeId": "vehicle_1",
                "vehicleIds": [f"v_{i+1}" for i in range(vehicle_count)],
                "profile": {
                    "matrix": "solomon_profile",
                    "scale": 1.0
                },
                "costs": {
                    "fixed": 0.0,
                    "distance": 1.0,
                    "time": 0.0
                },
                "shifts": [
                    {
                        "start": {
                            "earliest": depot['ready'],
                            "latest": depot['due'],
                            "location": {
                                "lat": depot['lat'],
                                "lng": depot['lng']
                            }
                        },
                        "end": {
                            "earliest": depot['ready'],
                            "latest": depot['due'],
                            "location": {
                                "lat": depot['lat'],
                                "lng": depot['lng']
                            }
                        }
                    }
                ],
                "capacity": [vehicle_capacity]
            }
        ]
    }

    return {
        "plan": {"jobs": jobs},
        "fleet": fleet
    }

def build_routing_matrix(nodes):
    n = len(nodes)
    flat_distances = [0.0] * (n * n)
    
    for i in range(n):
        for j in range(n):
            dx = nodes[i]['x'] - nodes[j]['x']
            dy = nodes[i]['y'] - nodes[j]['y']
            dist = math.sqrt(dx*dx + dy*dy)
            # Solomon uses distance as both distance and travel time.
            idx = i * n + j
            # Pragmatic format expects i64 (integers) for distances and travel times.
            # We scale by 10 to preserve 1 decimal of precision and round to nearest int.
            dist_int = int(round(dist * 10))
            flat_distances[idx] = dist_int
            
    return {
        "profile": "solomon_profile",
        "distances": flat_distances,
        "travelTimes": flat_distances
    }

def main():
    parser = argparse.ArgumentParser(description="Convert Solomon instance to Pragmatic JSON with fake lat/lng mapping but exact Euclidean matrices.")
    parser.add_argument("input", help="Path to Solomon .txt file")
    parser.add_argument("--out-dir", default=".", help="Output directory")
    
    # Default bounding box: A small area in central Beijing to make it look realistic on map
    parser.add_argument("--min-lng", type=float, default=116.30, help="Minimum Longitude")
    parser.add_argument("--min-lat", type=float, default=39.85, help="Minimum Latitude")
    parser.add_argument("--max-lng", type=float, default=116.45, help="Maximum Longitude")
    parser.add_argument("--max-lat", type=float, default=40.00, help="Maximum Latitude")
    
    args = parser.parse_args()
    
    print(f"Parsing {args.input}...")
    v_count, v_cap, nodes = parse_solomon(args.input)
    
    print(f"Parsed {len(nodes)} nodes, {v_count} vehicles (capacity: {v_cap}).")
    
    print(f"Mapping X/Y to Bounding Box: [{args.min_lng}, {args.max_lng}] x [{args.min_lat}, {args.max_lat}]")
    map_coordinates(nodes, args.min_lng, args.min_lat, args.max_lng, args.max_lat)
    
    base_name = os.path.basename(args.input).split('.')[0].lower()
    
    prob = build_pragmatic_problem(base_name, v_count, v_cap, nodes)
    mat = build_routing_matrix(nodes)
    
    prob_file = os.path.join(args.out_dir, f"{base_name}.problem.json")
    mat_file = os.path.join(args.out_dir, f"{base_name}.matrix.json")
    
    with open(prob_file, 'w') as f:
        json.dump(prob, f, indent=2)
    with open(mat_file, 'w') as f:
        json.dump(mat, f)
        
    print(f"Success! Wrote problem to {prob_file}")
    print(f"Success! Wrote matrix to {mat_file}")

if __name__ == "__main__":
    main()
