
# Rail Network Resilience

**Resilience and Efficiency in National Rail Networks: A Comparative Network Analysis of Japan and Switzerland**

A network science project analyzing the structural properties, resilience, and efficiency of national railway networks. This repository contains data processing pipelines, graph construction notebooks, and visualization tools for both the Japanese and Swiss rail systems.

## Datasets

### Japan: Ministry of Land, Infrastructure, Transport and Tourism (MLIT)

**Source:** [National Land Numerical Information - Railway Data (N02)](https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N02-2024.html)

The Japanese railway dataset (2024 edition) is provided by MLIT as part of their National Land Numerical Information initiative. It contains two primary GeoJSON files:

| File | Description | Geometry |
|------|-------------|----------|
| `N02-24_Station.geojson` | Station platforms | LineString |
| `N02-24_RailroadSection.geojson` | Railway track sections | LineString |

#### Key Attributes

**Stations (`N02_005*`):**
| Attribute | Name | Description |
|-----------|------|-------------|
| N02_001 | Railway classification | Differentiation by type of railway line. |
| N02_002 | Business type | Differentiation by railway line operators. |
| N02_003 | Route name | Name of the railway line |
| N02_004 | Operating company | A company that operates railway lines. |
| N02_005 | Station name | Name of the station |
| N02_005c | Station code | The unique number added by sorting the latitude of the station in descending order |
| N02_005g | Group code | A station within 300m and a station with the same name as a group, and the station code closest to the center of gravity of the group |

**Railroad Sections:**
| Attribute | Name | Description |
|-----------|------|-------------|
| N02_001| Railway classification | Differentiation by type of railway line. |
| N02_002 | Business type | Differentiation by railway line operators. |
| N02_003 | Route name | Name of the railway line |
| N02_004 | Operating company | A company that operates railway lines. |

#### Preprocessing Pipeline

The Japan notebook performs the following preprocessing steps:

1. **Platform Grouping**: Stations are grouped using the pre-computed `N02_005g` group code, which clusters platforms within 300m that share the same name.

2. **Interchange Merging**: Station groups sharing exact coordinates (interchange stations) are merged using a Union-Find algorithm to create single unified nodes.

3. **Spatial Snapping**: To handle floating-point precision issues in coordinate matching, a spatial snapping threshold of ~20cm (`2e-6°`) is applied when matching railroad endpoints to station coordinates.

4. **Graph Construction**: A NetworkX graph is built where:
   - **Station nodes**: Represent clustered station groups with attributes (name, operators, platform count, coordinates)
   - **Infrastructure nodes**: Created for railroad endpoints that don't match any station ()
   - **Edges**: Derived from railroad sections connecting stations

### Switzerland: SBB & swisstopo

The Swiss dataset supports two data sources (configurable via `DATA_SOURCE` in the notebook):

#### Option 1: SBB Infrastructure Data (`DATA_SOURCE = "sbb"`)

| File | Description |
|------|-------------|
| `sbb-linie-mit-betriebspunkten.csv` | Line topology with operational points |
| `sbb-dienststellen-gemass-opentransportdataswiss.csv` | Station metadata (Didok) |

Nodes are identified by station abbreviations and connected based on line topology ordered by kilometer markers.

#### Option 2: swisstopo Geodatabase (`DATA_SOURCE = "swisstopo"`)

| Layer | Description |
|-------|-------------|
| `Netzknoten` | Network nodes (stations and junctions) |
| `Netzsegment` | Network segments (track sections) |

**Source:** Federal Office of Topography (swisstopo) - `schienennetz_2056_de.gdb`

## Usage

### Building the Graphs

1. **Japan:**
   ```bash
   # Run all cells in Japan_dataset_exploration.ipynb
   # Output: datasets/japan/japan_rail_network.gpickle
   ```

2. **Switzerland:**
   ```bash
   # Set DATA_SOURCE in Swiss_dataset_exploration.ipynb
   # Run all cells
   # Output: datasets/switzerland/sbb_rail_network.gpickle (or swisstopo variant)
   ```

### Loading Pre-built Graphs

```python
import pickle
import networkx as nx

# Load Japan network
with open('datasets/japan/japan_rail_network.gpickle', 'rb') as f:
    G_japan = pickle.load(f)

# Load Swiss network
with open('datasets/switzerland/sbb_rail_network.gpickle', 'rb') as f:
    G_swiss = pickle.load(f)
```

### Visualization

Both notebooks include interactive Folium maps for exploring the networks. The Swiss dataset has a dedicated `Swiss_dataset_map.ipynb` for side-by-side comparison of SBB and swisstopo graphs.

## Graph Schema

### Node Attributes

| Attribute | Japan | Switzerland | Description |
|-----------|-------|-------------|-------------|
| `node_type` | ✓ | — | `'station'` or `'infrastructure'` |
| `is_station` | — | ✓ | Boolean station flag |
| `name` / `label` | ✓ | ✓ | Display name |
| `lat`, `lon` | ✓ | ✓ | WGS84 coordinates |
| `operators` | ✓ | — | List of operating companies |
| `platform_count` | ✓ | — | Number of platforms in group |
| `group_code` | ✓ | — | Original MLIT group code |
| `abbreviation` | — | ✓ | Station abbreviation (SBB) |

### Edge Attributes

| Attribute | Japan | Switzerland | Description |
|-----------|-------|-------------|-------------|
| `lines` | ✓ | ✓ | List of line names using this edge |
| `operator` | ✓ | — | Operating company |
| `source` | — | ✓ | Data source (`'sbb'` or `'swisstopo'`) |

## Git LFS

Large files (datasets, notebooks with outputs) are tracked with Git LFS. After cloning:

```bash
git lfs pull
```

## License

Dataset licenses are governed by their respective providers:
- **Japan (MLIT):** Subject to [National Land Numerical Information Terms of Use](https://nlftp.mlit.go.jp/ksj/other/agreement.html)
- **Switzerland (swisstopo):** Subject to [Swiss Open Government Data License](https://www.swisstopo.admin.ch/en/terms-of-use)