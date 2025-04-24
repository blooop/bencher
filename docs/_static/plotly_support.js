/* Custom JavaScript for Plotly support in Sphinx documentation */

// Initialize Plotly if it exists
document.addEventListener('DOMContentLoaded', function() {
  // Wait for the notebook cells to render
  setTimeout(function() {
    // Check if Plotly is loaded by the notebooks
    if (window.Plotly) {
      console.log("Plotly detected, ensuring proper initialization");
    } else if (window.requirejs) {
      // Try to load Plotly via requirejs if available
      requirejs.config({
        paths: {
          'plotly': 'https://cdn.plot.ly/plotly-latest.min'
        }
      });
      
      requirejs(['plotly'], function(Plotly) {
        console.log("Plotly loaded via requirejs");
        window.Plotly = Plotly;
      });
    }
  }, 1000);
});
