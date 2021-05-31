use chrono::Local;
use pyo3::prelude::*;
use pyo3::wrap_pyfunction;

/// Our timestamping function, accurate to milliseconds
#[pyfunction]
fn get_time() -> PyResult<String> {
    Ok(Local::now().format("%Y-%m-%d %H:%M:%S%.3f").to_string())
}

/// Create and initialize the utility submodule.
pub(crate) fn utility_submodule(py: Python) -> PyResult<&PyModule> {
    let module = PyModule::new(py, "utility")?;
    module.add_function(wrap_pyfunction!(get_time, module)?)?;

    return Ok(module);
}
