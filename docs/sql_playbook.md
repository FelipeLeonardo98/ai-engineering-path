# SQL Playbook For Customer Journey Analytics

This playbook teaches the local MCP agent how to translate common business questions into safe SQLite `SELECT` queries.

Use it as a semantic guide, not as executable application code. The agent should read this together with the live database schema before choosing the `query_readonly` MCP tool.

## Database Mental Model

The database represents a small customer journey analytics system.

### `customers`

One row per customer.

Important columns:

- `customer_id`: stable customer identifier.
- `full_name`: human-readable customer name.
- `segment`: commercial segment, such as `enterprise`, `mid-market`, or `startup`.
- `status`: customer status, such as `active` or `at_risk`.
- `current_channel`: latest known channel snapshot.

Use `customers` when the question is about the current state of customers.

Examples:

- How many customers are currently in WhatsApp?
- Which customers are active?
- How many customers are in each current channel?

### `customer_channel_events`

One row per customer interaction.

Important columns:

- `event_id`: stable event identifier.
- `customer_id`: customer connected to this event.
- `channel`: channel used in that interaction, such as `chat`, `whatsapp`, `email`, or `voice`.
- `event_timestamp`: chronological timestamp of the interaction.
- `event_type`: interaction type, such as `support_message`, `callback`, `follow_up`, or `document_sent`.
- `notes`: short human-readable event description.

Use `customer_channel_events` when the question is about journey, history, frequency, latest/earliest interactions, or channel usage over time.

Examples:

- Which channels did Carol use?
- What was Carol's last channel?
- Who interacted most frequently in voice?
- Which customer had the earliest interaction?

### `orders`

One row per order.

Important columns:

- `order_id`: stable order identifier.
- `customer_id`: customer connected to this order.
- `order_date`: order date.
- `amount_usd`: order value.
- `status`: order status, such as `paid`, `pending`, or `failed`.

Use `orders` when the question is about spending, revenue, paid orders, failed orders, or customer order value.

## Query Rules

- Always generate SQLite-compatible SQL.
- Only generate `SELECT` or `WITH` queries.
- Never generate `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `PRAGMA`, `ATTACH`, `DETACH`, `VACUUM`, or `REINDEX`.
- Use `LOWER(column)` for case-insensitive text filters.
- Use `LIKE '%name%'` for partial customer-name matching.
- Use `COUNT(*)` for frequency and count questions.
- Use `GROUP BY` when counting by customer, channel, segment, status, or event type.
- Use `ORDER BY ... ASC` for oldest/earliest/ascending questions.
- Use `ORDER BY ... DESC LIMIT 1` for latest/last/most recent questions.
- Join `customer_channel_events` to `customers` when the answer should include customer names.
- Join `orders` to `customers` when the answer should include customer names or segments.

## Examples

### 1. Count customers currently in WhatsApp

Question examples:

- How many customers are in WhatsApp?
- Quantos clientes estao no canal WhatsApp?

```sql
SELECT current_channel, COUNT(*) AS customer_count
FROM customers
WHERE LOWER(current_channel) = 'whatsapp'
GROUP BY current_channel;
```

### 2. Count customers currently in voice

Question examples:

- How many customers are in voice?
- Quantos clientes estao no canal voz?

```sql
SELECT current_channel, COUNT(*) AS customer_count
FROM customers
WHERE LOWER(current_channel) = 'voice'
GROUP BY current_channel;
```

### 3. Count customers by current channel

Question examples:

- How many customers are in each current channel?
- Quantos clientes existem por canal atual?

```sql
SELECT current_channel, COUNT(*) AS customer_count
FROM customers
GROUP BY current_channel
ORDER BY current_channel ASC;
```

### 4. List active customers

Question examples:

- Which customers are active?
- Liste os clientes ativos.

```sql
SELECT customer_id, full_name, segment, current_channel
FROM customers
WHERE LOWER(status) = 'active'
ORDER BY full_name ASC;
```

### 5. Count customers by segment

Question examples:

- How many customers are in each segment?
- Quantos clientes existem por segmento?

```sql
SELECT segment, COUNT(*) AS customer_count
FROM customers
GROUP BY segment
ORDER BY customer_count DESC, segment ASC;
```

### 6. Customer channel journey, oldest first

Question examples:

- Which channels did Carol use, oldest first?
- Por onde a cliente Carol passou em ordem crescente?

```sql
SELECT c.full_name, e.channel, e.event_timestamp, e.event_type
FROM customer_channel_events e
JOIN customers c ON c.customer_id = e.customer_id
WHERE LOWER(c.full_name) LIKE '%carol%'
ORDER BY e.event_timestamp ASC;
```

### 7. Customer channel journey, newest first

Question examples:

- Which channels did Bruno use, newest first?
- Por onde Bruno passou em ordem decrescente?

```sql
SELECT c.full_name, e.channel, e.event_timestamp, e.event_type
FROM customer_channel_events e
JOIN customers c ON c.customer_id = e.customer_id
WHERE LOWER(c.full_name) LIKE '%bruno%'
ORDER BY e.event_timestamp DESC;
```

### 8. Latest channel for a customer

Question examples:

- What was Carol's last channel?
- Qual foi o ultimo canal da Carol?

```sql
SELECT c.full_name, e.channel, e.event_timestamp, e.event_type
FROM customer_channel_events e
JOIN customers c ON c.customer_id = e.customer_id
WHERE LOWER(c.full_name) LIKE '%carol%'
ORDER BY e.event_timestamp DESC
LIMIT 1;
```

### 9. Earliest interaction overall

Question examples:

- Which customer had the earliest interaction?
- Qual cliente teve a primeira interacao?

```sql
SELECT c.full_name, e.channel, e.event_timestamp, e.event_type
FROM customer_channel_events e
JOIN customers c ON c.customer_id = e.customer_id
ORDER BY e.event_timestamp ASC
LIMIT 1;
```

### 10. Most frequent customer in a channel

Question examples:

- Find the most frequent customer_id in channel voice.
- Qual cliente apareceu mais vezes no canal voz?

```sql
SELECT e.customer_id, c.full_name, COUNT(*) AS interaction_count
FROM customer_channel_events e
JOIN customers c ON c.customer_id = e.customer_id
WHERE LOWER(e.channel) = 'voice'
GROUP BY e.customer_id, c.full_name
ORDER BY interaction_count DESC, c.full_name ASC
LIMIT 1;
```

### 11. Interaction count by customer for one channel

Question examples:

- Count interactions by customer in WhatsApp.
- Quantas interacoes cada cliente teve no WhatsApp?

```sql
SELECT e.customer_id, c.full_name, COUNT(*) AS interaction_count
FROM customer_channel_events e
JOIN customers c ON c.customer_id = e.customer_id
WHERE LOWER(e.channel) = 'whatsapp'
GROUP BY e.customer_id, c.full_name
ORDER BY interaction_count DESC, c.full_name ASC;
```

### 12. Interaction count by channel

Question examples:

- Which channel has the most interactions?
- Qual canal tem mais interacoes?

```sql
SELECT channel, COUNT(*) AS interaction_count
FROM customer_channel_events
GROUP BY channel
ORDER BY interaction_count DESC, channel ASC;
```

### 13. Latest interaction per customer

Question examples:

- What is the latest interaction for each customer?
- Qual foi a ultima interacao de cada cliente?

```sql
WITH latest_events AS (
    SELECT customer_id, MAX(event_timestamp) AS latest_timestamp
    FROM customer_channel_events
    GROUP BY customer_id
)
SELECT c.customer_id, c.full_name, e.channel, e.event_timestamp, e.event_type
FROM latest_events le
JOIN customer_channel_events e
    ON e.customer_id = le.customer_id
   AND e.event_timestamp = le.latest_timestamp
JOIN customers c ON c.customer_id = e.customer_id
ORDER BY c.full_name ASC;
```

### 14. Total paid amount by customer

Question examples:

- How much has each customer paid?
- Qual o valor pago por cliente?

```sql
SELECT c.customer_id, c.full_name, COALESCE(SUM(o.amount_usd), 0) AS paid_amount_usd
FROM customers c
LEFT JOIN orders o
    ON o.customer_id = c.customer_id
   AND LOWER(o.status) = 'paid'
GROUP BY c.customer_id, c.full_name
ORDER BY paid_amount_usd DESC, c.full_name ASC;
```

### 15. Highest-value paid customer

Question examples:

- Which customer paid the most?
- Qual cliente tem maior valor pago?

```sql
SELECT c.customer_id, c.full_name, COALESCE(SUM(o.amount_usd), 0) AS paid_amount_usd
FROM customers c
LEFT JOIN orders o
    ON o.customer_id = c.customer_id
   AND LOWER(o.status) = 'paid'
GROUP BY c.customer_id, c.full_name
ORDER BY paid_amount_usd DESC, c.full_name ASC
LIMIT 1;
```

## Common Interpretation Guide

Use this mapping when translating user language into SQL:

- "current channel" means `customers.current_channel`.
- "channel history", "journey", "passou", or "used channels" means `customer_channel_events`.
- "last", "latest", "ultimo", or "mais recente" means `ORDER BY event_timestamp DESC LIMIT 1`.
- "first", "earliest", "primeiro", or "mais antigo" means `ORDER BY event_timestamp ASC LIMIT 1`.
- "most frequent", "mais frequente", or "apareceu mais vezes" means `COUNT(*)`, `GROUP BY`, `ORDER BY count DESC`.
- "by customer" means group by `customer_id` and usually join `customers` for `full_name`.
- "by channel" means group by `channel` for event history, or `current_channel` for current snapshot.
- "spent", "paid", or "valor pago" means use `orders.amount_usd` and usually filter `orders.status = 'paid'`.
