// Offline Support JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Check if browser supports IndexedDB
    if (!window.indexedDB) {
        console.error("Your browser doesn't support IndexedDB. Offline functionality will not be available.");
        return;
    }
    
    // Initialize IndexedDB
    let db;
    const dbName = "kenyan_pos_offline";
    const dbVersion = 1;
    
    const request = indexedDB.open(dbName, dbVersion);
    
    // Error handler
    request.onerror = function(event) {
        console.error("Database error: " + event.target.errorCode);
    };
    
    // Success handler
    request.onsuccess = function(event) {
        db = event.target.result;
        console.log("IndexedDB initialized successfully");
        
        // Check connection status
        checkConnectionStatus();
        
        // Periodically check for pending offline transactions
        setInterval(syncOfflineTransactions, 30000); // Check every 30 seconds
    };
    
    // Set up the database structure
    request.onupgradeneeded = function(event) {
        const db = event.target.result;
        
        // Create object stores
        const offlineSalesStore = db.createObjectStore("offlineSales", { keyPath: "offline_id", autoIncrement: true });
        offlineSalesStore.createIndex("syncStatus", "syncStatus", { unique: false });
        
        const productsStore = db.createObjectStore("products", { keyPath: "id" });
        productsStore.createIndex("name", "name", { unique: false });
        productsStore.createIndex("barcode", "barcode", { unique: true });
        
        const customersStore = db.createObjectStore("customers", { keyPath: "id" });
        customersStore.createIndex("name", "name", { unique: false });
        customersStore.createIndex("phone", "phone", { unique: true });
        
        console.log("Database setup complete");
    };
    
    // Check connection status and update UI accordingly
    function checkConnectionStatus() {
        const isOnline = navigator.onLine;
        const statusIndicator = document.getElementById('connection-status');
        const offlineBanner = document.getElementById('offline-banner');
        
        if (statusIndicator) {
            if (isOnline) {
                statusIndicator.textContent = 'Online';
                statusIndicator.className = 'badge bg-success';
            } else {
                statusIndicator.textContent = 'Offline';
                statusIndicator.className = 'badge bg-danger';
            }
        }
        
        if (offlineBanner) {
            offlineBanner.style.display = isOnline ? 'none' : 'block';
        }
        
        // Cache product data when online
        if (isOnline) {
            cacheProductsData();
            cacheCustomersData();
        }
    }
    
    // Cache products data for offline use
    function cacheProductsData() {
        fetch('/api/products')
            .then(response => response.json())
            .then(products => {
                const transaction = db.transaction(["products"], "readwrite");
                const productsStore = transaction.objectStore("products");
                
                // Clear existing data
                productsStore.clear();
                
                // Add new data
                products.forEach(product => {
                    productsStore.add(product);
                });
                
                console.log(`Cached ${products.length} products for offline use`);
            })
            .catch(error => {
                console.error('Error caching products:', error);
            });
    }
    
    // Cache customers data for offline use
    function cacheCustomersData() {
        fetch('/api/customers')
            .then(response => response.json())
            .then(customers => {
                const transaction = db.transaction(["customers"], "readwrite");
                const customersStore = transaction.objectStore("customers");
                
                // Clear existing data
                customersStore.clear();
                
                // Add new data
                customers.forEach(customer => {
                    customersStore.add(customer);
                });
                
                console.log(`Cached ${customers.length} customers for offline use`);
            })
            .catch(error => {
                console.error('Error caching customers:', error);
            });
    }
    
    // Save sale data when offline
    window.saveOfflineSale = function(saleData) {
        return new Promise((resolve, reject) => {
            try {
                const transaction = db.transaction(["offlineSales"], "readwrite");
                const offlineSalesStore = transaction.objectStore("offlineSales");
                
                // Add timestamp and sync status
                saleData.timestamp = new Date().toISOString();
                saleData.syncStatus = "pending";
                
                // Generate offline reference
                saleData.offline_reference = "OFF-" + Math.random().toString(36).substr(2, 9).toUpperCase();
                
                const request = offlineSalesStore.add(saleData);
                
                request.onsuccess = function(event) {
                    console.log("Sale saved for offline synchronization");
                    resolve({
                        success: true,
                        message: "Sale saved for offline synchronization",
                        reference: saleData.offline_reference
                    });
                };
                
                request.onerror = function(event) {
                    console.error("Error saving offline sale:", event.target.error);
                    reject({
                        success: false,
                        message: "Error saving offline sale"
                    });
                };
            } catch (error) {
                console.error("Exception saving offline sale:", error);
                reject({
                    success: false,
                    message: "Exception saving offline sale"
                });
            }
        });
    };
    
    // Get products when offline
    window.getOfflineProducts = function(searchTerm = "") {
        return new Promise((resolve, reject) => {
            try {
                const transaction = db.transaction(["products"], "readonly");
                const productsStore = transaction.objectStore("products");
                const products = [];
                
                const request = productsStore.openCursor();
                
                request.onsuccess = function(event) {
                    const cursor = event.target.result;
                    
                    if (cursor) {
                        const product = cursor.value;
                        
                        // Filter by search term if provided
                        if (!searchTerm || 
                            product.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                            (product.barcode && product.barcode.includes(searchTerm))) {
                            products.push(product);
                        }
                        
                        cursor.continue();
                    } else {
                        resolve(products);
                    }
                };
                
                request.onerror = function(event) {
                    console.error("Error retrieving offline products:", event.target.error);
                    reject([]);
                };
            } catch (error) {
                console.error("Exception retrieving offline products:", error);
                reject([]);
            }
        });
    };
    
    // Get customers when offline
    window.getOfflineCustomers = function(searchTerm = "") {
        return new Promise((resolve, reject) => {
            try {
                const transaction = db.transaction(["customers"], "readonly");
                const customersStore = transaction.objectStore("customers");
                const customers = [];
                
                const request = customersStore.openCursor();
                
                request.onsuccess = function(event) {
                    const cursor = event.target.result;
                    
                    if (cursor) {
                        const customer = cursor.value;
                        
                        // Filter by search term if provided
                        if (!searchTerm || 
                            customer.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                            (customer.phone && customer.phone.includes(searchTerm))) {
                            customers.push(customer);
                        }
                        
                        cursor.continue();
                    } else {
                        resolve(customers);
                    }
                };
                
                request.onerror = function(event) {
                    console.error("Error retrieving offline customers:", event.target.error);
                    reject([]);
                };
            } catch (error) {
                console.error("Exception retrieving offline customers:", error);
                reject([]);
            }
        });
    };
    
    // Sync offline transactions when back online
    function syncOfflineTransactions() {
        if (!navigator.onLine) {
            return; // Skip if offline
        }
        
        try {
            const transaction = db.transaction(["offlineSales"], "readonly");
            const offlineSalesStore = transaction.objectStore("offlineSales");
            const pendingIndex = offlineSalesStore.index("syncStatus");
            const pendingRequest = pendingIndex.openCursor("pending");
            
            pendingRequest.onsuccess = function(event) {
                const cursor = event.target.result;
                
                if (cursor) {
                    const offlineSale = cursor.value;
                    
                    // Attempt to sync with server
                    syncSaleWithServer(offlineSale);
                    
                    cursor.continue();
                }
            };
        } catch (error) {
            console.error("Error syncing offline transactions:", error);
        }
    }
    
    // Sync a single sale with the server
    function syncSaleWithServer(offlineSale) {
        // Remove offline-specific properties
        const saleData = { ...offlineSale };
        delete saleData.offline_id;
        delete saleData.offline_reference;
        delete saleData.timestamp;
        delete saleData.syncStatus;
        
        fetch('/pos/checkout', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(saleData)
        })
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                // Update status to synced
                updateOfflineSaleStatus(offlineSale.offline_id, "synced", result.reference);
                console.log(`Offline sale ${offlineSale.offline_reference} synced successfully`);
            } else {
                // Mark as failed
                updateOfflineSaleStatus(offlineSale.offline_id, "failed", null, result.message);
                console.error(`Failed to sync offline sale: ${result.message}`);
            }
        })
        .catch(error => {
            // Keep as pending for retry
            console.error(`Error syncing offline sale: ${error}`);
        });
    }
    
    // Update offline sale status
    function updateOfflineSaleStatus(offlineId, status, serverReference = null, errorMessage = null) {
        try {
            const transaction = db.transaction(["offlineSales"], "readwrite");
            const offlineSalesStore = transaction.objectStore("offlineSales");
            
            const getRequest = offlineSalesStore.get(offlineId);
            
            getRequest.onsuccess = function(event) {
                const sale = event.target.result;
                if (sale) {
                    sale.syncStatus = status;
                    
                    if (serverReference) {
                        sale.server_reference = serverReference;
                    }
                    
                    if (errorMessage) {
                        sale.error_message = errorMessage;
                    }
                    
                    offlineSalesStore.put(sale);
                }
            };
        } catch (error) {
            console.error("Error updating offline sale status:", error);
        }
    }
    
    // Set up event listeners for online/offline events
    window.addEventListener('online', function() {
        checkConnectionStatus();
        syncOfflineTransactions();
    });
    
    window.addEventListener('offline', function() {
        checkConnectionStatus();
    });
});
