# Test Queries

## Single Database (select one)

### Basic
- How many customers are there?
- Show all products sorted by price descending
- List all orders with status 'cancelled' or 'refunded'

### Joins
- Show each customer's name and their total number of orders
- List all products that have never been ordered
- Show each order with the customer name and total items

### Aggregates
- What is the average order value by country?
- Show total revenue per product category
- Which city has the most VIP customers?

### Complex
- Top 5 products by total units sold
- Show profit margin (price - cost) / price for each product, sorted highest first
- Which customers have spent more than $2000 total?
- Average review rating per product, only products with 2+ reviews
- Monthly revenue trend for the last 3 months
- Which product categories have no reviews at all?
- Show the top 3 customers by number of distinct products purchased
- List products where current stock is less than total units sold

### Window Functions / CTEs
- Rank customers by total spend within each country
- For each category, show the best-selling and worst-selling product
- Show each order's percentage contribution to its customer's total spend

### Write Operations
- Insert a new customer named 'Test User' with email 'test@example.com' in city 'Boston'
- Update all products in the Accessories category to increase price by 10%
- Delete all cancelled orders

---

## Multi-Database (select both)

### Cross-Region Comparison
- How many customers are there?
- What is the total revenue?
- Show average order value
- Count orders by status
- How many products have stock below 50?

### Regional Deep Dives
- Top 3 customers by total spend
- Which product has the most reviews?
- Show revenue by product category
- Average review rating per product
- Total discount given across all orders
- Count of VIP vs premium vs standard customers
