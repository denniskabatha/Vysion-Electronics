// Inventory Management JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const inventoryTable = document.getElementById('inventory-table');
    const searchInput = document.getElementById('inventory-search');
    const filterSelect = document.getElementById('inventory-filter');
    const sortSelect = document.getElementById('inventory-sort');
    
    // Initialize event listeners if elements exist
    if (searchInput) {
        initSearch();
    }
    
    if (filterSelect) {
        initFilter();
    }
    
    if (sortSelect) {
        initSort();
    }
    
    if (inventoryTable) {
        initStockAdjustments();
    }
    
    // Initialize tooltips
    initTooltips();
    
    // Search functionality
    function initSearch() {
        searchInput.addEventListener('input', debounce(function() {
            filterInventoryTable();
        }, 300));
    }
    
    // Filter functionality
    function initFilter() {
        filterSelect.addEventListener('change', function() {
            filterInventoryTable();
        });
    }
    
    // Sort functionality
    function initSort() {
        sortSelect.addEventListener('change', function() {
            sortInventoryTable();
        });
    }
    
    // Filter and sort inventory table
    function filterInventoryTable() {
        const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
        const filterValue = filterSelect ? filterSelect.value : 'all';
        
        const rows = inventoryTable.querySelectorAll('tbody tr');
        
        rows.forEach(row => {
            const productName = row.querySelector('.product-name').textContent.toLowerCase();
            const category = row.querySelector('.product-category').textContent;
            const quantityText = row.querySelector('.product-quantity').textContent;
            const quantity = parseInt(quantityText);
            
            // Check if row matches search term
            const matchesSearch = productName.includes(searchTerm);
            
            // Check if row matches filter
            let matchesFilter = true;
            
            if (filterValue === 'low-stock') {
                const isLowStock = row.classList.contains('table-warning');
                matchesFilter = isLowStock;
            } else if (filterValue === 'out-of-stock') {
                matchesFilter = quantity <= 0;
            } else if (filterValue !== 'all') {
                // Filter by category
                matchesFilter = category === filterValue;
            }
            
            // Show/hide row based on search and filter
            row.style.display = matchesSearch && matchesFilter ? '' : 'none';
        });
    }
    
    // Sort inventory table
    function sortInventoryTable() {
        const sortValue = sortSelect.value;
        const [sortField, sortDirection] = sortValue.split('-');
        
        const tbody = inventoryTable.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        
        // Sort rows
        rows.sort((a, b) => {
            let aValue, bValue;
            
            if (sortField === 'name') {
                aValue = a.querySelector('.product-name').textContent;
                bValue = b.querySelector('.product-name').textContent;
                return sortDirection === 'asc' ? 
                    aValue.localeCompare(bValue) : 
                    bValue.localeCompare(aValue);
            } else if (sortField === 'quantity') {
                aValue = parseInt(a.querySelector('.product-quantity').textContent);
                bValue = parseInt(b.querySelector('.product-quantity').textContent);
            } else if (sortField === 'price') {
                aValue = parseFloat(a.querySelector('.product-price').getAttribute('data-price'));
                bValue = parseFloat(b.querySelector('.product-price').getAttribute('data-price'));
            }
            
            return sortDirection === 'asc' ? aValue - bValue : bValue - aValue;
        });
        
        // Re-append rows in sorted order
        rows.forEach(row => tbody.appendChild(row));
    }
    
    // Initialize stock adjustments
    function initStockAdjustments() {
        const adjustButtons = document.querySelectorAll('.adjust-stock-btn');
        
        adjustButtons.forEach(button => {
            button.addEventListener('click', function() {
                const productId = this.getAttribute('data-id');
                const productName = this.getAttribute('data-name');
                const currentStock = this.getAttribute('data-stock');
                
                showStockAdjustmentModal(productId, productName, currentStock);
            });
        });
    }
    
    // Show stock adjustment modal
    function showStockAdjustmentModal(productId, productName, currentStock) {
        const modal = document.createElement('div');
        modal.innerHTML = `
            <div class="modal fade" id="stockAdjustmentModal" tabindex="-1" aria-hidden="true">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Adjust Stock: ${productName}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <form id="stock-adjustment-form">
                                <input type="hidden" name="product_id" value="${productId}">
                                
                                <div class="mb-3">
                                    <label class="form-label">Current Stock:</label>
                                    <input type="text" class="form-control" value="${currentStock}" readonly>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="adjustment-type" class="form-label">Adjustment Type:</label>
                                    <select class="form-select" id="adjustment-type" name="adjustment_type">
                                        <option value="add">Add to Stock</option>
                                        <option value="remove">Remove from Stock</option>
                                        <option value="set">Set Stock Level</option>
                                    </select>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="adjustment-quantity" class="form-label">Quantity:</label>
                                    <input type="number" class="form-control" id="adjustment-quantity" 
                                           name="quantity" min="1" value="1" required>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="adjustment-reason" class="form-label">Reason:</label>
                                    <select class="form-select" id="adjustment-reason" name="reason">
                                        <option value="new_stock">New Stock</option>
                                        <option value="damaged">Damaged/Expired</option>
                                        <option value="correction">Inventory Correction</option>
                                        <option value="returned">Customer Return</option>
                                        <option value="other">Other</option>
                                    </select>
                                </div>
                                
                                <div class="mb-3" id="other-reason-container" style="display: none;">
                                    <label for="other-reason" class="form-label">Specify Reason:</label>
                                    <input type="text" class="form-control" id="other-reason" name="other_reason">
                                </div>
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" id="save-adjustment-btn">Save Adjustment</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Initialize modal
        const stockModal = new bootstrap.Modal(document.getElementById('stockAdjustmentModal'));
        stockModal.show();
        
        // Show other reason input if "Other" is selected
        const reasonSelect = document.getElementById('adjustment-reason');
        const otherReasonContainer = document.getElementById('other-reason-container');
        
        reasonSelect.addEventListener('change', function() {
            otherReasonContainer.style.display = this.value === 'other' ? 'block' : 'none';
        });
        
        // Save adjustment button handler
        document.getElementById('save-adjustment-btn').addEventListener('click', function() {
            const form = document.getElementById('stock-adjustment-form');
            const adjustmentType = form.elements['adjustment_type'].value;
            const quantity = parseInt(form.elements['quantity'].value);
            const reason = form.elements['reason'].value;
            const otherReason = form.elements['other_reason'].value;
            
            // Validate input
            if (quantity <= 0) {
                showAlert('Quantity must be greater than zero', 'warning');
                return;
            }
            
            if (reason === 'other' && !otherReason.trim()) {
                showAlert('Please specify the reason for adjustment', 'warning');
                return;
            }
            
            // Disable button and show loading
            this.disabled = true;
            this.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Saving...';
            
            // In a real implementation, this would submit to the server
            // For this demo, we'll simulate a server response
            setTimeout(() => {
                // Close modal
                stockModal.hide();
                
                // Show success message
                showAlert('Stock adjustment saved successfully', 'success');
                
                // Update the UI (in a real implementation, we would reload or update only the relevant row)
                let newStock = parseInt(currentStock);
                
                if (adjustmentType === 'add') {
                    newStock += quantity;
                } else if (adjustmentType === 'remove') {
                    newStock = Math.max(0, newStock - quantity);
                } else if (adjustmentType === 'set') {
                    newStock = quantity;
                }
                
                // Update the row in the table
                const row = document.querySelector(`tr[data-product-id="${productId}"]`);
                if (row) {
                    row.querySelector('.product-quantity').textContent = newStock;
                    
                    // Update button attribute
                    const button = row.querySelector('.adjust-stock-btn');
                    button.setAttribute('data-stock', newStock);
                    
                    // Update row styling based on stock level
                    const reorderLevel = parseInt(row.getAttribute('data-reorder-level')) || 5;
                    
                    row.classList.remove('table-danger', 'table-warning');
                    
                    if (newStock <= 0) {
                        row.classList.add('table-danger');
                    } else if (newStock <= reorderLevel) {
                        row.classList.add('table-warning');
                    }
                }
                
                // In a real implementation, we would reload data from the server
                // or update only the affected parts of the UI
            }, 1000);
        });
        
        // Remove modal when hidden
        document.getElementById('stockAdjustmentModal').addEventListener('hidden.bs.modal', function() {
            this.remove();
        });
    }
    
    // Initialize tooltips
    function initTooltips() {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
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
    
    // Debounce function to limit API calls
    function debounce(func, wait) {
        let timeout;
        return function() {
            const context = this;
            const args = arguments;
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(context, args), wait);
        };
    }
});
