# Geospatial Mappings in Navigation via (Knowledge)GraphRAG

A sophisticated navigation system that leverages geospatial data, knowledge graphs, and retrieval-augmented generation (GraphRAG) to provide personalized route recommendations. This project combines OpenStreetMap data with user preference profiling and natural language processing to rank routes based on individual preferences, historical behavior, and contextual factors.

## Features

- **Personalized Route Ranking**: Rank multiple route options using user profiles built from historical navigation data
- **Multi-Modal Ranking**: Support for prompt-based (text preference), profile-based (historical data), and hybrid ranking modes
- **Geospatial Analysis**: Utilizes OpenStreetMap data with OSMnx for accurate routing and feature extraction
- **Temporal Context Awareness**: Considers time of day, season, and other contextual factors in route scoring
- **RESTful API**: FastAPI-based web service for easy integration
- **Sentence Embeddings**: Uses Sentence Transformers for semantic matching of route descriptions to user preferences
- **Data Processing**: Scripts for processing GeoLife trajectory data into user history profiles

## Installation

### Prerequisites

- Python 3.8+
- Access to OpenStreetMap data (handled automatically via OSMnx)

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd "Geospatial Mappings in Navigation via (Knowledge)GraphRAG"
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. (Optional) Set up user history data path:
```bash
export GEOROUTE_USER_HISTORY_PATH=/path/to/your/user_histories.json
```

## Usage

### Running the API Server

Start the FastAPI server:
```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

### API Endpoints

#### GET /
Health check endpoint.

#### POST /rank-routes
Rank routes between two locations based on user preferences.

**Request Body:**
```json
{
  "origin": "New York, NY",
  "destination": "Boston, MA",
  "preference": "I prefer scenic routes with minimal traffic",
  "user_id": "user123",
  "request_datetime": "2023-10-15T14:30:00Z",
  "dist_meters": 4000,
  "k_routes": 5,
  "ranking_mode": "hybrid"
}
```

**Parameters:**
- `origin`: Starting location (address string, lat/lon dict, or [lat, lon] list)
- `destination`: Ending location (same format as origin)
- `preference`: Text description of route preferences (required for "prompt" and "hybrid" modes)
- `user_id`: User identifier (required for "profile" and "hybrid" modes)
- `request_datetime`: ISO 8601 datetime string for temporal context
- `dist_meters`: Search radius around origin/destination (default: 4000)
- `k_routes`: Number of route candidates to generate and rank (default: 5)
- `ranking_mode`: "prompt", "profile", or "hybrid"

**Response:**
```json
{
  "origin": "New York, NY",
  "destination": "Boston, MA",
  "preference": "I prefer scenic routes with minimal traffic",
  "user_id": "user123",
  "ranking_mode": "hybrid",
  "context": {...},
  "profile_summary": "User prefers residential streets during afternoon hours...",
  "routes": [
    {
      "rank": 1,
      "combined_score": 0.85,
      "profile_score": 0.9,
      "sbert_score": 0.75,
      "distance_km": 12.5,
      "major_pct": 0.2,
      "walk_pct": 0.1,
      "residential_pct": 0.6,
      "service_pct": 0.1,
      "intersections": 45,
      "turns": 12,
      "park_near_pct": 0.3,
      "min_park_dist_m": 50.0,
      "safety_score": 0.8,
      "lit_pct": 0.9,
      "signal_cnt": 8,
      "crossing_cnt": 15,
      "tunnel_m": 0.0,
      "summary": "A residential route with good lighting and park access",
      "coordinates": [[40.7128, -74.0060], ...]
    }
  ]
}
```

### Interactive API Documentation

Visit `http://localhost:8000/docs` for interactive Swagger UI documentation.

## Project Structure

```
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── app/                      # Main application code
│   ├── __init__.py
│   ├── main.py              # FastAPI application and route ranking logic
│   ├── routing.py           # Route generation and feature extraction
│   ├── profile.py           # User profile building and context analysis
│   ├── ranking.py           # Route ranking using sentence embeddings
│   └── schemas.py           # Pydantic models for API requests/responses
├── cache/                    # Cached OpenStreetMap data
├── data/                     # Processed user history data
├── docs/                     # Documentation files
├── geolife_raw/              # Raw GeoLife trajectory dataset
├── misc/                     # Miscellaneous files
├── plots/                    # Generated plots and visualizations
└── scripts/                  # Data processing and evaluation scripts
    ├── build_geolife_histories.py     # Process GeoLife data into user profiles
    ├── build_geolife_histories_osm.py # OSM-enhanced profile building
    ├── evaluate_geolife_profiles.py   # Profile evaluation scripts
    └── osm_history_probe.py           # OSM data probing utilities
```

## Data Processing

The project uses the [GeoLife trajectory dataset](https://www.microsoft.com/en-us/research/publication/geolife-gps-trajectory-dataset-user-guide/) for building user profiles. To process the data:

1. Place GeoLife data in `geolife_raw/Data/`
2. Run the processing scripts:
```bash
python scripts/build_geolife_histories.py
python scripts/build_geolife_histories_osm.py
```

This generates user history files in JSON format with route preferences inferred from historical navigation patterns.

## Route Features

Routes are analyzed for various features that influence ranking:

- **Distance and Path Type**: Total distance, percentages of major roads, walkways, residential streets, service roads
- **Connectivity**: Number of intersections and turns
- **Amenities**: Proximity to parks, minimum park distance
- **Safety**: Safety scores based on road types and lighting
- **Infrastructure**: Street lighting percentage, traffic signals, pedestrian crossings, tunnels

## Ranking Modes

### Prompt Mode
Ranks routes based on semantic similarity between route descriptions and user-provided preference text using sentence embeddings.

### Profile Mode
Builds user profiles from historical navigation data and scores routes based on learned preferences, considering temporal context.

### Hybrid Mode
Combines profile-based and prompt-based ranking for optimal personalization.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

[Add appropriate license information]

## Acknowledgments

- GeoLife dataset for trajectory data
- OpenStreetMap and OSMnx for geospatial data
- Sentence Transformers for embedding-based ranking
- FastAPI for the web framework