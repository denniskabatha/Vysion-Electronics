// Dashboard JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Charts
    initializeSalesChart();
    initializeInventoryChart();
    initializePaymentMethodsChart();
    
    // Initialize date range picker if it exists
    const dateRangePicker = document.getElementById('date-range-picker');
    if (dateRangePicker) {
        initializeDateRangePicker();
    }
    
    // Function to initialize sales chart
    function initializeSalesChart() {
        const salesChartCanvas = document.getElementById('sales-chart');
        
        if (!salesChartCanvas) return;
        
        // Sample data - in a real implementation, this would come from the server
        const salesData = {
            labels: getLast7Days(),
            datasets: [{
                label: 'Sales (KES)',
                data: [12500, 19000, 15000, 17500, 21000, 18500, 25000],
                backgroundColor: 'rgba(54, 162, 235, 0.2)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 2,
                tension: 0.4
            }]
        };
        
        const salesChart = new Chart(salesChartCanvas, {
            type: 'line',
            data: salesData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return 'KES ' + value.toLocaleString();
                            }
                        }
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return 'KES ' + context.parsed.y.toLocaleString();
                            }
                        }
                    }
                }
            }
        });
    }
    
    // Function to initialize inventory chart
    function initializeInventoryChart() {
        const inventoryChartCanvas = document.getElementById('inventory-chart');
        
        if (!inventoryChartCanvas) return;
        
        // Sample data - in a real implementation, this would come from the server
        const inventoryData = {
            labels: ['Groceries', 'Electronics', 'Household', 'Beverages', 'Personal Care'],
            datasets: [{
                label: 'Items in Stock',
                data: [120, 45, 78, 90, 60],
                backgroundColor: [
                    'rgba(255, 99, 132, 0.6)',
                    'rgba(54, 162, 235, 0.6)',
                    'rgba(255, 206, 86, 0.6)',
                    'rgba(75, 192, 192, 0.6)',
                    'rgba(153, 102, 255, 0.6)'
                ],
                borderColor: [
                    'rgba(255, 99, 132, 1)',
                    'rgba(54, 162, 235, 1)',
                    'rgba(255, 206, 86, 1)',
                    'rgba(75, 192, 192, 1)',
                    'rgba(153, 102, 255, 1)'
                ],
                borderWidth: 1
            }]
        };
        
        const inventoryChart = new Chart(inventoryChartCanvas, {
            type: 'doughnut',
            data: inventoryData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }
    
    // Function to initialize payment methods chart
    function initializePaymentMethodsChart() {
        const paymentChartCanvas = document.getElementById('payment-methods-chart');
        
        if (!paymentChartCanvas) return;
        
        // Sample data - in a real implementation, this would come from the server
        const paymentData = {
            labels: ['M-Pesa', 'Cash', 'Card'],
            datasets: [{
                label: 'Payment Methods',
                data: [65, 20, 15],
                backgroundColor: [
                    'rgba(75, 192, 192, 0.6)',
                    'rgba(255, 206, 86, 0.6)',
                    'rgba(153, 102, 255, 0.6)'
                ],
                borderColor: [
                    'rgba(75, 192, 192, 1)',
                    'rgba(255, 206, 86, 1)',
                    'rgba(153, 102, 255, 1)'
                ],
                borderWidth: 1
            }]
        };
        
        const paymentChart = new Chart(paymentChartCanvas, {
            type: 'pie',
            data: paymentData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const value = context.parsed;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = Math.round((value / total) * 100);
                                return `${context.label}: ${percentage}%`;
                            }
                        }
                    }
                }
            }
        });
    }
    
    // Function to initialize date range picker
    function initializeDateRangePicker() {
        // In a real implementation, this would be implemented with a date picker library
        // For this demo, we'll use basic inputs
        const startDateInput = document.getElementById('start-date');
        const endDateInput = document.getElementById('end-date');
        const applyDateRangeBtn = document.getElementById('apply-date-range');
        
        if (startDateInput && endDateInput && applyDateRangeBtn) {
            // Set default dates if not already set
            if (!startDateInput.value) {
                const today = new Date();
                const oneWeekAgo = new Date();
                oneWeekAgo.setDate(today.getDate() - 7);
                
                startDateInput.value = formatDate(oneWeekAgo);
                endDateInput.value = formatDate(today);
            }
            
            // Apply button handler
            applyDateRangeBtn.addEventListener('click', function() {
                const startDate = startDateInput.value;
                const endDate = endDateInput.value;
                
                if (!startDate || !endDate) {
                    showAlert('Please select both start and end dates', 'warning');
                    return;
                }
                
                // Validate date range
                if (new Date(startDate) > new Date(endDate)) {
                    showAlert('Start date cannot be after end date', 'warning');
                    return;
                }
                
                // In a real implementation, this would reload the dashboard with the new date range
                showAlert('Date range applied: ' + startDate + ' to ' + endDate, 'success');
                
                // Optionally, reload the page with query parameters
                const currentUrl = new URL(window.location.href);
                currentUrl.searchParams.set('start_date', startDate);
                currentUrl.searchParams.set('end_date', endDate);
                window.location.href = currentUrl.toString();
            });
        }
    }
    
    // Helper function to get the last 7 days as labels
    function getLast7Days() {
        const result = [];
        for (let i = 6; i >= 0; i--) {
            const date = new Date();
            date.setDate(date.getDate() - i);
            result.push(formatShortDate(date));
        }
        return result;
    }
    
    // Helper function to format date as YYYY-MM-DD
    function formatDate(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }
    
    // Helper function to format date as MMM DD
    function formatShortDate(date) {
        const options = { month: 'short', day: 'numeric' };
        return date.toLocaleDateString('en-US', options);
    }
    
    // Helper function to show alerts
    function showAlert(message, type = 'info') {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed top-0 end-0 m-3`;
        alertDiv.setAttribute('role', 'alert');
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        document.body.appendChild(alertDiv);
        
        // Auto-dismiss after 3 seconds
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alertDiv);
            bsAlert.close();
        }, 3000);
    }
});
