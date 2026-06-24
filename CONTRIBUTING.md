# Contributing to render

Thanks for considering contributing! This document explains how to contribute code, tests, documentation, and examples to this repository.

## Contribution types

- Renderers/Converters: add or improve scripts in `render/*/*_converter.py` that transform data outputs (from experiments, model outputs, or observational data) into datacubes.
- Notebooks: add tutorial or example notebooks demonstrating conversion steps and analysis. Jupyter notebooks are preferred.
- Documentation: update README, add how-tos, or improve docstrings.
- Example Data: small example inputs and expected outputs can be housed on Zenodo. If you upload a dataset to Zenodo, use `pooch` to fetch the data in your example, and keep downloads small (<100MB). See more detailed instructions below.

## Workflow

1. Fork the repository and create a branch from 'main' with a descriptive name (`feature/`, `fix/`, `docs/`).
2. Add your example, make a fix, or add your renderer in the appropriate location.
3. Commit changes with clear messages and open a pull request describing intent and the contribution
4. Respond to maintainer requests for changes.
5. **Important**, add a section to the CONTENTS.md document describing your addition. 

## Coding style

- Prefer clear, idiomatic code with ample comments and meaningful variable names.
- Keep functions small and focused; add docstrings in Google style.

## Notebooks

- Notebooks should be committed in cleared state (output cells removed) when possible, or include a small dataset to reproduce results.
- Include a short introductory cell at the top describing the notebook purpose and data/software requirements.

## Example datasets: fetch them with `pooch`

For reproducible examples, store example datasets on an external hosting service (e.g. Zenodo) and fetch them at runtime using `pooch`.

Minimal usage examples:

- Simple one-off retrieve:

```python
import pooch


url = "https://example.org/data/sample.nc"
hash_ = "md5:0123456789abcdef0123456789abcdef"
local_path = pooch.retrieve(url, hash_, fname="sample.nc", path=pooch.os_cache("render"))
```

If it is your first download, you can specify `hash=None`

- Using a small registry and a Pooch instance (recommended for multiple files):

```python
from pooch import create

REGISTRY = {"sample.nc": "md5:0123456789abcdef0123456789abcdef"}

data_pooch = create(
	path=pooch.os_cache("render"),
	base_url="https://my-bucket.example.org/datasets/",
	registry=REGISTRY,
)

local = data_pooch.fetch("sample.nc")
```

Notes:

- Add `pooch` to `requirements.txt` or your environment when examples/tests rely on it:

```text
pooch>=1.6.0
```
- Use cryptographic hashes (SHA256 or MD5) in the registry for integrity checks.
- Keep hosted example datasets small or provide download instructions for large datasets.

## Reporting issues

- Open issues for bugs or feature requests with steps to reproduce and minimal working example data when possible.

## Review and PRs

- PRs should be focused and include tests or examples demonstrating the change.
- Be responsive to review feedback; maintainers may request style or test updates.

## Contact

Open an issue or a PR; maintainers will review and respond.

