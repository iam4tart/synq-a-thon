import re, os
import pandas as pd

with open('src/context_store.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add trips dictionary
content = content.replace('self.interview_citations: Dict[str, str] = {}', 'self.interview_citations: Dict[str, str] = {}\n        self.trips_by_vehicle: Dict[str, list] = {}')

# Add _load_trips call
content = content.replace('self._load_interview_transcript()', 'self._load_interview_transcript()\n        self._load_trips()')

# Add _load_trips function and is_vehicle_currently_assigned
methods = '''
    def _load_trips(self):
        path = self._find_path("meridian_trips.csv")
        if not path or not os.path.exists(path):
            return
        # Using pandas to read trips
        try:
            df = pd.read_csv(path, usecols=["vehicle_reg", "dispatch_time", "delivery_time", "status"])
            for _, row in df.iterrows():
                canonical_plate = EntityResolver.canonicalize_plate(str(row.get("vehicle_reg", "")))
                if not canonical_plate:
                    continue
                if canonical_plate not in self.trips_by_vehicle:
                    self.trips_by_vehicle[canonical_plate] = []
                    
                dispatch_time = None
                delivery_time = None
                try:
                    if pd.notnull(row.get("dispatch_time")):
                        dispatch_time = pd.to_datetime(row["dispatch_time"]).tz_localize(None)
                    if pd.notnull(row.get("delivery_time")):
                        delivery_time = pd.to_datetime(row["delivery_time"]).tz_localize(None)
                except Exception:
                    pass
                    
                self.trips_by_vehicle[canonical_plate].append({
                    "dispatch_time": dispatch_time,
                    "delivery_time": delivery_time,
                    "status": str(row.get("status", "")).strip().upper()
                })
        except Exception as e:
            pass

    def is_vehicle_currently_assigned(self, canonical_plate: str, as_of_time: datetime) -> bool:
        """Returns True if the vehicle is currently on a trip at the given time."""
        trips = self.trips_by_vehicle.get(canonical_plate, [])
        if isinstance(as_of_time, str):
            try:
                as_of_time = pd.to_datetime(as_of_time)
            except Exception:
                as_of_time = datetime.now()
        as_of_time_naive = as_of_time.replace(tzinfo=None) if isinstance(as_of_time, datetime) else pd.to_datetime(as_of_time).tz_localize(None)
        
        for trip in trips:
            status = trip.get("status", "")
            if status == "IN_TRANSIT":
                return True
                
            dispatch = trip.get("dispatch_time")
            delivery = trip.get("delivery_time")
            
            if dispatch and delivery:
                if dispatch <= as_of_time_naive <= delivery:
                    return True
            elif dispatch and status != "COMPLETED":
                if dispatch <= as_of_time_naive:
                    return True
        return False
'''

if 'def _load_trips' not in content:
    content = content.replace('def get_vehicle', methods.strip() + '\n\n    def get_vehicle')
    
with open('src/context_store.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Patched context_store.py!')
