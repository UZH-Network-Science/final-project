# Resilience and Efficiency in National Rail Networks

*A Comparative Network Analysis of the Japanese and Swiss Railway Systems*

---

This documentation site presents the results of a network science study investigating the topography, efficiency, and resilience of two national railway networks: **Japan** and **Switzerland**. The analysis employs graph-theoretic methods to quantify network topology and simulate failure scenarios, enabling a systematic comparison of how each network responds to targeted and random disruptions.

## Interactive Exploration

The Comparison Analysis notebook is available as a [live interactive application](https://network-science.obermaier.dev), allowing you to explore robustness simulations and network visualizations dynamically.

## Navigate the Analysis

The documentation is organized into the following sections:

### Analysis

| Notebook | Description |
|----------|-------------|
| **Comparison** ([static](./analysis/Comparison_Analysis.ipynb), [interactive](https://network-science.obermaier.dev)) | Side-by-side comparison of topological metrics, degree distributions, and robustness under various attack strategies |
| [**Japan**](./analysis/Japan_Analysis.ipynb) | Detailed analysis of the Japanese rail network including efficiency decay and extended robustness metrics |
| [**Switzerland**](./analysis/Switzerland_Analysis.ipynb) | Detailed analysis of the Swiss rail network with equivalent metrics for cross-country comparison |

### Preprocessing

| Notebook | Description |
|----------|-------------|
| [**Japan Construction**](./preprocessing/Japan_Construction_Story.ipynb) | Data processing pipeline for the MLIT railway dataset, including station grouping and graph construction |
| [**Switzerland Construction**](./preprocessing/Switzerland_Construction_Story.ipynb) | Data processing pipeline for the swisstopo geodatabase, including spatial merging and transfer edge generation |

## About

This work was conducted as part of the Network Science course at the University of Zurich. For a complete discussion of methodology, preprocessing decisions, and analytical interpretation, please refer to the accompanying academic report.
