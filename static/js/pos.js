// POS Management JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Cart data structure
    let cart = {
        items: [],
        customerId: null,
        subtotal: 0,
        taxAmount: 0,
        discountAmount: 0,
        totalAmount: 0
    };

    // DOM Elements
    const productSearchInput = document.getElementById('product-search');
    const productResults = document.getElementById('product-results');
    const cartItemsContainer = document.getElementById('cart-items');
    const cartSubtotal = document.getElementById('cart-subtotal');
    const cartTax = document.getElementById('cart-tax');
    const cartDiscount = document.getElementById('cart-discount');
    const cartTotal = document.getElementById('cart-total');
    const customerSelect = document.getElementById('customer-select');
    const barcodeInput = document.getElementById('barcode-input');
    const checkoutBtn = document.getElementById('checkout-btn');
    const clearCartBtn = document.getElementById('clear-cart-btn');
    const categoryFilter = document.getElementById('category-filter');

    // Initialize event listeners
    if (productSearchInput) {
        initProductSearch();
    }

    if (barcodeInput) {
        initBarcodeScanning();
    }

    if (categoryFilter) {
        initCategoryFilter();
    }

    if (customerSelect) {
        initCustomerSelect();
    }

    if (checkoutBtn) {
        initCheckout();
    }

    if (clearCartBtn) {
        clearCartBtn.addEventListener('click', clearCart);
    }

    // Load products initially
    loadProducts();

    // Function to initialize product search
    function initProductSearch() {
        productSearchInput.addEventListener('input', debounce(function() {
            if (productSearchInput.value.length > 2) {
                searchProducts(productSearchInput.value);
            } else if (productSearchInput.value.length === 0) {
                loadProducts(); // Load all products if search cleared
            }
        }, 300));
    }

    // Function to initialize barcode scanning
    function initBarcodeScanning() {
        barcodeInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                searchProductsByBarcode(barcodeInput.value);
                barcodeInput.value = '';
            }
        });
    }

    // Function to initialize category filter
    function initCategoryFilter() {
        categoryFilter.addEventListener('change', function() {
            loadProducts(this.value);
        });
    }

    // Function to initialize customer select
    function initCustomerSelect() {
        customerSelect.addEventListener('change', function() {
            cart.customerId = this.value !== "" ? parseInt(this.value) : null;
        });
    }

    // Function to initialize checkout
    function initCheckout() {
        checkoutBtn.addEventListener('click', showCheckoutModal);
    }

    // Load all products or filter by category
    function loadProducts(categoryId = null) {
        let url = '/api/products';
        if (categoryId) {
            url += `?category=${categoryId}`;
        }

        fetch(url)
            .then(response => response.json())
            .then(products => {
                displayProducts(products);
            })
            .catch(error => {
                console.error('Error loading products:', error);
                showAlert('Failed to load products. Please try again.', 'danger');
            });
    }

    // Search products by name or code
    function searchProducts(query) {
        fetch(`/api/products?q=${encodeURIComponent(query)}`)
            .then(response => response.json())
            .then(products => {
                displayProducts(products);
            })
            .catch(error => {
                console.error('Error searching products:', error);
            });
    }

    // Search products by barcode
    function searchProductsByBarcode(barcode) {
        fetch(`/api/products?q=${encodeURIComponent(barcode)}`)
            .then(response => response.json())
            .then(products => {
                if (products.length > 0) {
                    // If product found, add directly to cart
                    addToCart(products[0]);
                } else {
                    showAlert('Product not found', 'warning');
                }
            })
            .catch(error => {
                console.error('Error searching by barcode:', error);
                showAlert('Error scanning barcode', 'danger');
            });
    }

    // Display products in grid
    function displayProducts(products) {
        productResults.innerHTML = '';
        
        if (products.length === 0) {
            productResults.innerHTML = '<div class="col-12 text-center py-4">No products found</div>';
            return;
        }

        products.forEach(product => {
            const productCard = document.createElement('div');
            productCard.className = 'col-md-4 col-lg-3 mb-3';
            productCard.innerHTML = `
                <div class="card h-100">
                    <div class="card-body">
                        <h6 class="card-title">${product.name}</h6>
                        <p class="card-text">
                            ${formatCurrency(product.price)}<br>
                            <small>Stock: ${product.quantity_available}</small>
                        </p>
                    </div>
                    <div class="card-footer bg-transparent border-top-0">
                        <button class="btn btn-sm btn-primary add-to-cart" 
                                data-id="${product.id}"
                                ${product.quantity_available <= 0 ? 'disabled' : ''}>
                            Add to Cart
                        </button>
                    </div>
                </div>
            `;
            
            const addButton = productCard.querySelector('.add-to-cart');
            addButton.addEventListener('click', () => addToCart(product));
            
            productResults.appendChild(productCard);
        });
    }

    // Add product to cart
    function addToCart(product) {
        // Check if product already in cart
        const existingItemIndex = cart.items.findIndex(item => item.product_id === product.id);
        
        if (existingItemIndex !== -1) {
            // If quantity available is exceeded, show warning
            if (cart.items[existingItemIndex].quantity >= product.quantity_available) {
                showAlert('Cannot add more of this item. Stock limit reached.', 'warning');
                return;
            }
            
            // Update quantity of existing item
            cart.items[existingItemIndex].quantity++;
            cart.items[existingItemIndex].total_price = 
                calculateItemTotal(cart.items[existingItemIndex].unit_price, 
                                  cart.items[existingItemIndex].quantity,
                                  cart.items[existingItemIndex].tax_rate);
        } else {
            // Add new item to cart
            const itemTaxRate = product.tax_rate || 0;
            const unitPrice = product.price || 0;
            
            cart.items.push({
                product_id: product.id,
                name: product.name,
                quantity: 1,
                unit_price: unitPrice,
                tax_rate: itemTaxRate,
                discount_amount: 0,
                total_price: calculateItemTotal(unitPrice, 1, itemTaxRate)
            });
        }
        
        // Update cart display
        updateCart();
        showAlert(`Added ${product.name} to cart`, 'success');
    }

    // Calculate total price for an item
    function calculateItemTotal(unitPrice, quantity, taxRate = 0, discountAmount = 0) {
        const subtotal = unitPrice * quantity;
        const taxAmount = subtotal * (taxRate / 100);
        return subtotal + taxAmount - discountAmount;
    }

    // Update cart display and totals
    function updateCart() {
        // Clear current cart display
        cartItemsContainer.innerHTML = '';
        
        if (cart.items.length === 0) {
            cartItemsContainer.innerHTML = '<tr><td colspan="6" class="text-center">Cart is empty</td></tr>';
            updateCartTotals(0, 0, 0, 0);
            checkoutBtn.disabled = true;
            return;
        }
        
        // Enable checkout button
        checkoutBtn.disabled = false;
        
        // Calculate cart totals
        let subtotal = 0;
        let taxAmount = 0;
        
        // Add items to cart display
        cart.items.forEach((item, index) => {
            const row = document.createElement('tr');
            
            // Calculate item values
            const itemSubtotal = item.unit_price * item.quantity;
            const itemTax = itemSubtotal * (item.tax_rate / 100);
            
            subtotal += itemSubtotal;
            taxAmount += itemTax;
            
            row.innerHTML = `
                <td>${item.name}</td>
                <td>${formatCurrency(item.unit_price)}</td>
                <td>
                    <div class="input-group input-group-sm">
                        <button class="btn btn-outline-secondary decrease-qty" type="button">-</button>
                        <input type="text" class="form-control form-control-sm text-center item-quantity" value="${item.quantity}" readonly>
                        <button class="btn btn-outline-secondary increase-qty" type="button">+</button>
                    </div>
                </td>
                <td>${item.tax_rate}%</td>
                <td>${formatCurrency(item.total_price)}</td>
                <td>
                    <button class="btn btn-sm btn-danger remove-item">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            `;
            
            // Add event listeners for quantity changes
            const decreaseBtn = row.querySelector('.decrease-qty');
            const increaseBtn = row.querySelector('.increase-qty');
            const removeBtn = row.querySelector('.remove-item');
            
            decreaseBtn.addEventListener('click', () => changeQuantity(index, -1));
            increaseBtn.addEventListener('click', () => changeQuantity(index, 1));
            removeBtn.addEventListener('click', () => removeItem(index));
            
            cartItemsContainer.appendChild(row);
        });
        
        // Update cart totals
        updateCartTotals(subtotal, taxAmount, cart.discountAmount);
    }

    // Update cart total values
    function updateCartTotals(subtotal, taxAmount, discountAmount = 0) {
        cart.subtotal = subtotal;
        cart.taxAmount = taxAmount;
        cart.discountAmount = discountAmount;
        cart.totalAmount = subtotal + taxAmount - discountAmount;
        
        // Display formatted totals
        cartSubtotal.textContent = formatCurrency(subtotal);
        cartTax.textContent = formatCurrency(taxAmount);
        cartDiscount.textContent = formatCurrency(discountAmount);
        cartTotal.textContent = formatCurrency(cart.totalAmount);
    }

    // Change quantity of item in cart
    function changeQuantity(index, change) {
        const item = cart.items[index];
        const newQuantity = item.quantity + change;
        
        // Ensure quantity is at least 1
        if (newQuantity < 1) {
            return;
        }
        
        // Check stock availability
        fetch(`/api/products?q=${encodeURIComponent(item.name)}`)
            .then(response => response.json())
            .then(products => {
                if (products.length > 0) {
                    const product = products.find(p => p.id === item.product_id);
                    
                    if (product && newQuantity > product.quantity_available) {
                        showAlert('Cannot add more of this item. Stock limit reached.', 'warning');
                        return;
                    }
                    
                    // Update quantity and total
                    item.quantity = newQuantity;
                    item.total_price = calculateItemTotal(
                        item.unit_price, item.quantity, item.tax_rate, item.discount_amount
                    );
                    
                    // Update cart display
                    updateCart();
                }
            })
            .catch(error => {
                console.error('Error checking stock:', error);
                showAlert('Error checking stock availability', 'danger');
            });
    }

    // Remove item from cart
    function removeItem(index) {
        cart.items.splice(index, 1);
        updateCart();
        showAlert('Item removed from cart', 'info');
    }

    // Clear entire cart
    function clearCart() {
        cart.items = [];
        cart.customerId = null;
        updateCart();
        
        // Reset customer select if it exists
        if (customerSelect) {
            customerSelect.value = "";
        }
        
        showAlert('Cart cleared', 'info');
    }

    // Show checkout modal with payment options
    function showCheckoutModal() {
        if (cart.items.length === 0) {
            showAlert('Cannot checkout with empty cart', 'warning');
            return;
        }
        
        // Create modal dynamically
        const modal = document.createElement('div');
        modal.innerHTML = `
            <div class="modal fade" id="checkoutModal" tabindex="-1" aria-hidden="true">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Complete Sale</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <div class="mb-3">
                                <p><strong>Total Amount:</strong> ${formatCurrency(cart.totalAmount)}</p>
                                <p><strong>Items:</strong> ${cart.items.length}</p>
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label">Payment Method</label>
                                <div class="d-flex payment-method-buttons">
                                    <button type="button" class="btn btn-outline-primary me-2 payment-method-btn" data-method="cash">
                                        Cash
                                    </button>
                                    <button type="button" class="btn btn-outline-primary me-2 payment-method-btn" data-method="mpesa">
                                        M-Pesa
                                    </button>
                                    <button type="button" class="btn btn-outline-primary payment-method-btn" data-method="card">
                                        Card
                                    </button>
                                </div>
                            </div>
                            
                            <div id="mpesa-details" class="payment-details" style="display: none;">
                                <div class="mb-3">
                                    <label for="mpesa-phone" class="form-label">M-Pesa Phone Number</label>
                                    <input type="tel" class="form-control" id="mpesa-phone" placeholder="e.g., 0712345678">
                                    <div class="form-text">Enter the phone number to receive M-Pesa payment request</div>
                                </div>
                            </div>
                            
                            <div id="cash-details" class="payment-details" style="display: none;">
                                <div class="mb-3">
                                    <label for="cash-tendered" class="form-label">Cash Tendered</label>
                                    <input type="number" class="form-control" id="cash-tendered" min="${cart.totalAmount}" step="0.01">
                                </div>
                                <div class="mb-3">
                                    <label for="cash-change" class="form-label">Change</label>
                                    <input type="text" class="form-control" id="cash-change" readonly>
                                </div>
                            </div>
                            
                            <div id="card-details" class="payment-details" style="display: none;">
                                <div class="mb-3">
                                    <p>Process card payment through terminal</p>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" id="process-payment-btn" disabled>Process Payment</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Initialize modal
        const checkoutModal = new bootstrap.Modal(document.getElementById('checkoutModal'));
        checkoutModal.show();
        
        // Set up payment method selection
        const paymentMethodButtons = document.querySelectorAll('.payment-method-btn');
        const paymentDetails = document.querySelectorAll('.payment-details');
        const processPaymentBtn = document.getElementById('process-payment-btn');
        let selectedPaymentMethod = null;
        
        paymentMethodButtons.forEach(button => {
            button.addEventListener('click', function() {
                const method = this.getAttribute('data-method');
                
                // Reset all buttons and hide all details
                paymentMethodButtons.forEach(btn => btn.classList.remove('active', 'btn-primary'));
                paymentMethodButtons.forEach(btn => btn.classList.add('btn-outline-primary'));
                paymentDetails.forEach(detail => detail.style.display = 'none');
                
                // Highlight selected button and show relevant details
                this.classList.remove('btn-outline-primary');
                this.classList.add('active', 'btn-primary');
                document.getElementById(`${method}-details`).style.display = 'block';
                
                selectedPaymentMethod = method;
                processPaymentBtn.disabled = false;
            });
        });
        
        // Handle cash change calculation
        const cashTenderedInput = document.getElementById('cash-tendered');
        const cashChangeInput = document.getElementById('cash-change');
        
        if (cashTenderedInput) {
            cashTenderedInput.addEventListener('input', function() {
                const tendered = parseFloat(this.value) || 0;
                const change = tendered - cart.totalAmount;
                cashChangeInput.value = change >= 0 ? formatCurrency(change) : 'Insufficient amount';
                processPaymentBtn.disabled = change < 0;
            });
        }
        
        // Process payment button handler
        processPaymentBtn.addEventListener('click', function() {
            if (!selectedPaymentMethod) {
                return;
            }
            
            if (selectedPaymentMethod === 'mpesa') {
                processMpesaPayment();
            } else {
                processRegularPayment(selectedPaymentMethod);
            }
        });
        
        // Process regular payment (cash/card)
        function processRegularPayment(method) {
            processPaymentBtn.disabled = true;
            processPaymentBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';
            
            // Create payment data
            const paymentData = {
                items: cart.items,
                customer_id: cart.customerId,
                payment_method: method,
                subtotal: cart.subtotal,
                tax_amount: cart.taxAmount,
                discount_amount: cart.discountAmount,
                total_amount: cart.totalAmount
            };
            
            // Send checkout request
            fetch('/pos/checkout', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(paymentData)
            })
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    // Close modal
                    checkoutModal.hide();
                    
                    // Show receipt or success message
                    showReceiptModal(result.reference, selectedPaymentMethod, cart.totalAmount);
                    
                    // Clear cart
                    clearCart();
                } else {
                    showAlert('Payment failed: ' + result.message, 'danger');
                    processPaymentBtn.disabled = false;
                    processPaymentBtn.textContent = 'Process Payment';
                }
            })
            .catch(error => {
                console.error('Error processing payment:', error);
                showAlert('Error processing payment', 'danger');
                processPaymentBtn.disabled = false;
                processPaymentBtn.textContent = 'Process Payment';
            });
        }
        
        // Process M-Pesa payment
        function processMpesaPayment() {
            const phoneInput = document.getElementById('mpesa-phone');
            const phoneNumber = phoneInput.value.trim();
            
            if (!phoneNumber) {
                showAlert('Please enter a valid phone number', 'warning');
                return;
            }
            
            // Disable button and show loading
            processPaymentBtn.disabled = true;
            processPaymentBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';
            
            // First create the sale record
            const saleData = {
                items: cart.items,
                customer_id: cart.customerId,
                payment_method: 'mpesa',
                subtotal: cart.subtotal,
                tax_amount: cart.taxAmount,
                discount_amount: cart.discountAmount,
                total_amount: cart.totalAmount
            };
            
            fetch('/pos/checkout', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(saleData)
            })
            .then(response => response.json())
            .then(saleResult => {
                if (saleResult.success) {
                    // Now initiate M-Pesa payment
                    const mpesaData = {
                        sale_id: saleResult.sale_id,
                        phone: phoneNumber,
                        amount: cart.totalAmount
                    };
                    
                    return fetch('/pos/mpesa-payment', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify(mpesaData)
                    })
                    .then(response => response.json())
                    .then(mpesaResult => {
                        if (mpesaResult.success) {
                            // Close checkout modal
                            checkoutModal.hide();
                            
                            // Show M-Pesa waiting modal
                            showMpesaWaitingModal(saleResult.reference, mpesaResult.checkout_request_id);
                            
                            // Clear cart
                            clearCart();
                        } else {
                            showAlert('M-Pesa payment failed: ' + mpesaResult.message, 'danger');
                            processPaymentBtn.disabled = false;
                            processPaymentBtn.textContent = 'Process Payment';
                        }
                    });
                } else {
                    showAlert('Sale creation failed: ' + saleResult.message, 'danger');
                    processPaymentBtn.disabled = false;
                    processPaymentBtn.textContent = 'Process Payment';
                }
            })
            .catch(error => {
                console.error('Error processing M-Pesa payment:', error);
                showAlert('Error processing payment', 'danger');
                processPaymentBtn.disabled = false;
                processPaymentBtn.textContent = 'Process Payment';
            });
        }
        
        // Remove modal when hidden
        document.getElementById('checkoutModal').addEventListener('hidden.bs.modal', function() {
            this.remove();
        });
    }
    
    // Show M-Pesa waiting modal
    function showMpesaWaitingModal(reference, checkoutRequestId) {
        const modal = document.createElement('div');
        modal.innerHTML = `
            <div class="modal fade" id="mpesaWaitingModal" data-bs-backdrop="static" tabindex="-1" aria-hidden="true">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">M-Pesa Payment</h5>
                        </div>
                        <div class="modal-body text-center">
                            <div class="my-4">
                                <div class="spinner-border text-primary" role="status">
                                    <span class="visually-hidden">Loading...</span>
                                </div>
                                <p class="mt-3" id="mpesa-status-message">Waiting for M-Pesa payment confirmation...</p>
                                <p>Please check your phone and enter M-Pesa PIN when prompted</p>
                            </div>
                            <div>
                                <p><strong>Sale Reference:</strong> ${reference}</p>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" id="mpesa-done-btn">Done</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Initialize modal
        const mpesaModal = new bootstrap.Modal(document.getElementById('mpesaWaitingModal'));
        mpesaModal.show();
        
        // Set up polling for payment status
        const statusMessage = document.getElementById('mpesa-status-message');
        const pollInterval = 5000; // 5 seconds
        let pollCount = 0;
        const maxPolls = 12; // 1 minute maximum wait
        
        const checkStatus = () => {
            fetch(`/pos/check-payment-status/${checkoutRequestId}`)
                .then(response => response.json())
                .then(result => {
                    pollCount++;
                    
                    if (result.success) {
                        if (result.is_complete) {
                            // Payment complete
                            clearInterval(pollTimer);
                            
                            if (result.status === 'completed') {
                                statusMessage.textContent = 'Payment successful!';
                                statusMessage.className = 'mt-3 text-success';
                            } else {
                                statusMessage.textContent = 'Payment failed or cancelled';
                                statusMessage.className = 'mt-3 text-danger';
                            }
                        } else if (pollCount >= maxPolls) {
                            // Timeout
                            clearInterval(pollTimer);
                            statusMessage.textContent = 'Payment pending. Check sales records for updates.';
                            statusMessage.className = 'mt-3 text-warning';
                        }
                    } else {
                        // Error checking status
                        clearInterval(pollTimer);
                        statusMessage.textContent = 'Error checking payment status';
                        statusMessage.className = 'mt-3 text-danger';
                    }
                })
                .catch(error => {
                    console.error('Error checking payment status:', error);
                    clearInterval(pollTimer);
                    statusMessage.textContent = 'Error checking payment status';
                    statusMessage.className = 'mt-3 text-danger';
                });
        };
        
        // Start polling
        const pollTimer = setInterval(checkStatus, pollInterval);
        checkStatus(); // Check immediately
        
        // Done button handler
        document.getElementById('mpesa-done-btn').addEventListener('click', function() {
            clearInterval(pollTimer);
            mpesaModal.hide();
        });
        
        // Remove modal when hidden
        document.getElementById('mpesaWaitingModal').addEventListener('hidden.bs.modal', function() {
            this.remove();
        });
    }
    
    // Show receipt modal
    function showReceiptModal(reference, paymentMethod, amount) {
        const modal = document.createElement('div');
        modal.innerHTML = `
            <div class="modal fade" id="receiptModal" tabindex="-1" aria-hidden="true">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Receipt</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body text-center">
                            <div class="mb-4">
                                <i class="fas fa-check-circle text-success fa-3x"></i>
                                <h4 class="mt-2">Payment Successful</h4>
                            </div>
                            <div>
                                <p><strong>Sale Reference:</strong> ${reference}</p>
                                <p><strong>Payment Method:</strong> ${paymentMethod.toUpperCase()}</p>
                                <p><strong>Amount:</strong> ${formatCurrency(amount)}</p>
                                <p><strong>Date:</strong> ${new Date().toLocaleString()}</p>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-primary" id="print-receipt-btn">
                                <i class="fas fa-print"></i> Print Receipt
                            </button>
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Initialize modal
        const receiptModal = new bootstrap.Modal(document.getElementById('receiptModal'));
        receiptModal.show();
        
        // Print handler
        document.getElementById('print-receipt-btn').addEventListener('click', function() {
            // In a real implementation, this would print the receipt
            window.print();
        });
        
        // Remove modal when hidden
        document.getElementById('receiptModal').addEventListener('hidden.bs.modal', function() {
            this.remove();
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
    
    // Helper to format currency
    function formatCurrency(amount) {
        return new Intl.NumberFormat('en-KE', {
            style: 'currency',
            currency: 'KES'
        }).format(amount);
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
