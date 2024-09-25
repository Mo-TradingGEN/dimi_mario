const app = Vue.createApp({
  data() {
    return {
      message: 'Welcome to TradingGEN!',
      ticker: '',
      companyInfo: null, // Stores the company information from the backend
      newsMessage: '',
      summaryMessage: '',
      weeklySummaryMessage: '',
      newsSuccess: false,
      summarySuccess: false,
      weeklySummarySuccess: false,
      loading: false, // Indicator to show the process is running
      searchError: false // To handle error scenarios
    };
  },
  methods: {
    // Search company information based on the ticker
    async searchCompany() {
      if (!this.ticker) {
        this.message = "Please enter a valid ticker!";
        this.searchError = true;
        return;
      }
      this.loading = true;  // Start loading
      try {
        console.log(`Searching for company: ${this.ticker}`);  // Debugging log
        const response = await fetch(`/search/${this.ticker}`); // API call to Flask backend
        
        if (!response.ok) {
          throw new Error("Company not found");
        }

        const data = await response.json(); // Parse JSON response
        console.log("Company data received:", data);  // Debugging log to see the data received
        this.companyInfo = data;  // Assign received data to companyInfo
        this.message = `Found company info for ${this.ticker}`;
        this.searchError = false;
      } catch (error) {
        console.error("Error fetching company info:", error);
        this.message = "Error: Company not found or server issue!";
        this.searchError = true;
      } finally {
        this.loading = false;  // Stop loading
      }
    },

    // Fetch news for the given ticker
    async fetchNews() {
      if (!this.ticker) {
        this.newsMessage = "Please enter a valid ticker!";
        this.newsSuccess = false;
        return;
      }
      this.loading = true;
      try {
        const response = await fetch(`/fetch_news/${this.ticker}`, { method: 'POST' });
        if (!response.ok) {
          throw new Error("News fetching failed");
        }
        const data = await response.json();
        this.newsMessage = data.message;
        this.newsSuccess = true;
      } catch (error) {
        console.error("Error fetching news:", error);
        this.newsMessage = "Error: Unable to fetch news!";
        this.newsSuccess = false;
      } finally {
        this.loading = false;
      }
    },

    // Generate a daily summary for the ticker
    async generateSummary() {
      if (!this.ticker) {
        this.summaryMessage = "Please enter a valid ticker!";
        this.summarySuccess = false;
        return;
      }
      this.loading = true;
      try {
        const response = await fetch(`/summarize`, { method: 'POST' });
        if (!response.ok) {
          throw new Error("Summary generation failed");
        }
        const data = await response.json();
        this.summaryMessage = data.message;
        this.summarySuccess = true;
      } catch (error) {
        console.error("Error generating summary:", error);
        this.summaryMessage = "Error: Unable to generate summary!";
        this.summarySuccess = false;
      } finally {
        this.loading = false;
      }
    },

    // Generate a weekly summary for the ticker
    async generateWeeklySummary() {
      if (!this.ticker) {
        this.weeklySummaryMessage = "Please enter a valid ticker!";
        this.weeklySummarySuccess = false;
        return;
      }
      this.loading = true;
      try {
        const response = await fetch(`/weekly_summary/${this.ticker}`, { method: 'POST' });
        if (!response.ok) {
          throw new Error("Weekly summary generation failed");
        }
        const data = await response.json();
        this.weeklySummaryMessage = data.message;
        this.weeklySummarySuccess = true;
      } catch (error) {
        console.error("Error generating weekly summary:", error);
        this.weeklySummaryMessage = "Error: Unable to generate weekly summary!";
        this.weeklySummarySuccess = false;
      } finally {
        this.loading = false;
      }
    }
  }
});

// Mount the Vue app to the #app div
app.mount('#app');