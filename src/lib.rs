mod utility;

use pyo3::prelude::*;

#[pymodule]
fn rs_rd_tool(py: Python, module: &PyModule) -> PyResult<()> {
    module.add_submodule(utility::utility_submodule(py)?)?;

    Ok(())
}
