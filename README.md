# render

**Converters, datacubes, and example workflows for creating sandsuet-compliant data from your current data.**

## Introduction

This repository contains a variety of tools so to convert geomorphologic data from various sources (satellite imagery, aerial imageray, repeat lidar, model outputs, experimental topography, etc.) into `sandsuet`-compliant NetCDF files. These scripts and example notebooks demonstrate the conversion and basic post-processing to create analysis-ready datacubes. The aim is to provide reproducible, well-tested converters (renderers) that users can reuse or adapt for visualization, machine learning, or further geospatial analysis.

## Contribution types

- **Renderers/Converters:** Scripts that read data that derive from other systems (could be model outputs, experimental data, etc.) and produce sandsuet-compliant datacubes (e.g. `delft3d_dat_converter.py`, `delft3d_converter.py`).
- **Notebooks:** Example workflows and tutorials demonstrating conversion and light analysis (Jupyter notebooks in each folder).
- **Documentation:** Usage examples, table of contents, how-to guides.
- **Examples / Data:** Small sample datasets and expected outputs for testing and demos stored on external repositories like Zenodo. Document these by adding a notebook that showcases the product.

## How to contribute

1. Fork the repository and create a feature branch.
2. Add or update code, examples, and documentation.
3. Open a pull request describing the change and linking relevant issues.
4. Test that your links and code run as expected. 

For detailed contribution guidelines, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Contact

For questions or contributions, open an issue or submit a pull request.

Maintained by the Sandpiper Team
