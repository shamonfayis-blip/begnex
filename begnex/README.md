# Begnex - Django E-Commerce Website

## Overview

Begnex is a full-stack e-commerce web application developed using Django. It provides a complete online shopping experience for customers and an advanced admin panel for managing products, categories, variants, offers, coupons, orders, users, and sales reports.

The application is hosted on AWS EC2 using Gunicorn and Nginx with PostgreSQL as the database.

---

# Features

## User Module

- User Registration
- Login & Logout
- Google Authentication
- OTP Verification
- Forgot Password
- Reset Password
- User Profile Management
- Edit Profile
- Change Password

## Product Module

- Product Listing
- Product Details
- Product Variants
- Multiple Product Images
- Product Search
- Product Sorting
- Category Filter
- Price Filter
- Stock Availability

## Wishlist

- Add to Wishlist
- Remove from Wishlist
- Move Wishlist Items to Cart

## Cart

- Add to Cart
- Remove Items
- Quantity Update
- Stock Validation

## Address Management

- Add Address
- Edit Address
- Delete Address
- Multiple Shipping Addresses

## Checkout

- Order Summary
- Coupon Apply
- Wallet Payment
- Razorpay Payment
- Cash on Delivery
- Address Selection

## Orders

- Place Order
- Order History
- Order Details
- Cancel Order
- Return Order
- Download Invoice

## Wallet

- Wallet Balance
- Wallet Transactions
- Refund Support

---

# Admin Features

## Dashboard

- Dashboard Overview
- Sales Summary

## User Management

- View Users
- Block / Unblock Users

## Category Management

- Add Category
- Edit Category
- List / Unlist Category

## Product Management

- Add Product
- Edit Product
- Delete Product
- Manage Product Images
- Manage Variants

## Coupon Management

- Create Coupons
- Edit Coupons
- Activate / Deactivate Coupons

## Offer Management

- Product Offers
- Category Offers

## Order Management

- View Orders
- Update Order Status
- Cancel Orders
- Return Management

## Sales Report

- Daily Report
- Weekly Report
- Monthly Report
- Custom Date Report

---

# Tech Stack

## Backend

- Python
- Django

## Frontend

- HTML
- CSS
- Bootstrap
- JavaScript

## Database

- PostgreSQL

## Authentication

- Django Authentication
- Google OAuth (django-allauth)

## Payment Gateway

- Razorpay

## Server

- AWS EC2 (Ubuntu)

## Web Server

- Nginx

## Application Server

- Gunicorn

## Version Control

- Git
- GitHub

---

# Installation

Clone Repository

```bash
git clone https://github.com/shamonfayis-blip/begnex.git
```

Move into project

```bash
cd begnex
```

Create Virtual Environment

```bash
python -m venv venv
```

Activate Virtual Environment

Windows

```bash
venv\Scripts\activate
```

Linux

```bash
source venv/bin/activate
```

Install Dependencies

```bash
pip install -r requirements.txt
```

---

# Environment Variables

Create a `.env` file and configure:

- SECRET_KEY
- DEBUG
- DATABASE_NAME
- DATABASE_USER
- DATABASE_PASSWORD
- DATABASE_HOST
- DATABASE_PORT
- EMAIL_HOST_USER
- EMAIL_HOST_PASSWORD
- GOOGLE_CLIENT_ID
- GOOGLE_CLIENT_SECRET
- RAZORPAY_KEY_ID
- RAZORPAY_KEY_SECRET

---

# Running the Project

Apply migrations

```bash
python manage.py migrate
```

Collect static files

```bash
python manage.py collectstatic
```

Run development server

```bash
python manage.py runserver
```

---

# Deployment

The project is deployed using:

- AWS EC2 (Ubuntu)
- Gunicorn
- Nginx
- PostgreSQL
- Let's Encrypt SSL
- Hostinger DNS

Deployment Steps

1. Push code to GitHub
2. SSH into EC2
3. Pull latest code

```bash
git pull origin main
```

4. Activate virtual environment

```bash
source venv/bin/activate
```

5. Install dependencies

```bash
pip install -r requirements.txt
```

6. Apply migrations

```bash
python manage.py migrate
```

7. Collect static files

```bash
python manage.py collectstatic --noinput
```

8. Restart Gunicorn

```bash
sudo systemctl restart gunicorn
```

9. Restart Nginx

```bash
sudo systemctl restart nginx
```

---

# Live Demo

https://fayis.space

---

# GitHub Repository

https://github.com/shamonfayis-blip/begnex

---

# Author

Fayis