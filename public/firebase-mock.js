/**
 * WateLetric - Firebase Web SDK Mock
 * Intercepts Firestore queries and routes them to python server.py REST APIs
 * for seamless out-of-the-box local operation.
 */
(function() {
    console.log("WateLetric Firebase Emulator Mock Initialized.");
    
    // Save reference to the real Firebase SDK instance if it exists
    const realFirebase = window.firebase;
    
    const firebaseMock = {
        initializeApp: function(config) {
            console.log("Firebase App Initialized with Config:", config);
            this.config = config;
            if (realFirebase && typeof realFirebase.initializeApp === "function") {
                realFirebase.initializeApp(config);
            }
            return this;
        },
        auth: function() {
            if (realFirebase && typeof realFirebase.auth === "function") {
                return realFirebase.auth();
            }
            // Fallback mock auth object
            return {
                onAuthStateChanged: function(cb) {
                    // Instantly trigger with null (no user logged in)
                    setTimeout(() => cb(null), 0);
                    return () => {};
                },
                signInWithEmailAndPassword: function(email, password) {
                    console.log("Sign-in simulated", email);
                    return Promise.resolve({ user: { email } });
                },
                createUserWithEmailAndPassword: function(email, password) {
                    console.log("Sign-up simulated", email);
                    return Promise.resolve({ user: { email } });
                },
                signOut: function() {
                    return Promise.resolve();
                }
            };
        },
        firestore: function() {
            return {
                collection: function(collectionName) {
                    return {
                        _collectionName: collectionName,
                        _filters: [],
                        _orderBy: null,
                        
                        where: function(field, op, val) {
                            this._filters.push({ field, op, val });
                            return this;
                        },
                        
                        orderBy: function(field) {
                            this._orderBy = field;
                            return this;
                        },
                        
                        onSnapshot: function(callback) {
                            let day = 1;
                            let utility = "electricity";
                            
                            this._filters.forEach(f => {
                                if (f.field === "day") day = f.val;
                                if (f.field === "utility_type") utility = f.val;
                            });
                            
                            const fetchData = () => {
                                // If simulation is running, return simulated stream array
                                if (window.realtimeInterval && window.simulatedIntervals) {
                                    const docs = window.simulatedIntervals.map((interval, idx) => ({
                                        id: `${utility}_${day}_interval_${idx}`,
                                        data: () => ({
                                            day: day,
                                            utility_type: utility,
                                            time: interval.time,
                                            time_str: interval.time_str,
                                            value: interval.electricity_kwh || interval.water_liters || interval.value,
                                            predicted: interval.predicted,
                                            anomaly: interval.anomaly
                                        })
                                    }));
                                    callback({
                                        forEach: (cb) => docs.forEach(cb),
                                        docs: docs,
                                        size: docs.length,
                                        empty: docs.length === 0
                                    });
                                    return;
                                }
                                
                                fetch(`/api/usage?utility=${utility}&day=${day}`)
                                    .then(res => res.json())
                                    .then(data => {
                                        const docs = [];
                                        if (data && data.intervals) {
                                            data.intervals.forEach((interval, idx) => {
                                                docs.push({
                                                    id: `${utility}_${day}_interval_${idx}`,
                                                    data: () => ({
                                                        day: day,
                                                        utility_type: utility,
                                                        time: interval.time,
                                                        time_str: interval.time_str,
                                                        value: interval.value,
                                                        predicted: interval.predicted,
                                                        anomaly: interval.anomaly
                                                    })
                                                });
                                            });
                                        }
                                        
                                        callback({
                                            forEach: (cb) => docs.forEach(cb),
                                            docs: docs,
                                            size: docs.length,
                                            empty: docs.length === 0
                                        });
                                    })
                                    .catch(err => {
                                        console.warn("REST API fallback triggers. Reading window.billingData...");
                                        const fallbackData = window.billingData && window.billingData[day] && window.billingData[day][utility];
                                        if (fallbackData) {
                                            const docs = fallbackData.intervals.map((interval, idx) => ({
                                                id: `${utility}_${day}_interval_${idx}`,
                                                data: () => ({
                                                    day: day,
                                                    utility_type: utility,
                                                    time: interval.time,
                                                    time_str: interval.time_str,
                                                    value: interval.electricity_kwh || interval.water_liters || interval.value,
                                                    predicted: interval.predicted,
                                                    anomaly: interval.anomaly
                                                })
                                            }));
                                            callback({
                                                forEach: (cb) => docs.forEach(cb),
                                                docs: docs,
                                                size: docs.length,
                                                empty: docs.length === 0
                                            });
                                        }
                                    });
                            };
                            
                            // Load initial data
                            fetchData();
                            
                            // Listen to window-level dispatch events for updating simulation updates in real-time
                            const onUpdate = () => fetchData();
                            window.addEventListener("firestore-update", onUpdate);
                            
                            // Return unsubscribe function
                            return () => {
                                window.removeEventListener("firestore-update", onUpdate);
                            };
                        },
                        
                        doc: function(docId) {
                            return {
                                onSnapshot: function(callback) {
                                    // Parse day and utility from docId e.g. "day1_electricity"
                                    const parts = docId.split("_");
                                    const day = parseInt(parts[0].replace("day", "")) || 1;
                                    const utility = parts[1] || "electricity";
                                    
                                    const fetchSummary = () => {
                                        fetch(`/api/summary?utility=${utility}&day=${day}`)
                                            .then(res => res.json())
                                            .then(data => {
                                                callback({
                                                    exists: true,
                                                    data: () => data
                                                });
                                            })
                                            .catch(err => {
                                                const fallbackData = window.billingData && window.billingData[day] && window.billingData[day][utility];
                                                if (fallbackData) {
                                                    callback({
                                                        exists: true,
                                                        data: () => fallbackData
                                                    });
                                                }
                                            });
                                    };
                                    
                                    fetchSummary();
                                    
                                    const onUpdate = () => fetchSummary();
                                    window.addEventListener("firestore-update", onUpdate);
                                    
                                    return () => {
                                        window.removeEventListener("firestore-update", onUpdate);
                                    };
                                }
                            };
                        }
                    };
                }
            };
        }
    };
    
    // Mount mock global object
    window.firebase = firebaseMock;
})();
