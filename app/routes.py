from app import app
from app import utils
import requests
import os
import io
import json
import pandas as pd
import numpy as np
from datetime import datetime
from bs4 import BeautifulSoup
from matplotlib import pyplot as plt
from flask import render_template, request, redirect, url_for, send_file, jsonify

@app.route('/')
def index():
    return render_template('index.html.jinja')

@app.route('/extract', methods=['POST', 'GET'])
def extract():
    if request.method == 'POST':
        product_id = request.form.get('product_id')
        # 94103927
        url = f'https://www.ceneo.pl/{product_id}'
        response = requests.get(url)

        if response.status_code == requests.codes['ok']:
            page_dom = BeautifulSoup(response.text, 'html.parser')
            opinions_count = utils.extract(page_dom, '.product-review__link > span')
            if opinions_count:
                product_name = utils.extract(page_dom, 'h1')
                url = f'https://www.ceneo.pl/{product_id}#tab=reviews'
                all_opinions = []
                while url:
                    response = requests.get(url)
                    page_dom = BeautifulSoup(response.text, "html.parser")
                    opinions = page_dom.select('div.js_product-review')    
                    for opinion in opinions:
                        single_opinion = {
                            key: utils.extract(opinion, *value)
                                for key, value in utils.selectors.items()
                        }
                        all_opinions.append(single_opinion)
                    
                    try:
                        url = 'https://www.ceneo.pl' + utils.extract(page_dom, 'a.pagination__next', 'href')
                        # print(url)
                    except TypeError:
                        url = None
                    if not os.path.exists('app/data'):
                        os.mkdir('app/data')
                    if not os.path.exists('app/data/opinions'):
                        os.mkdir('app/data/opinions')
                    with open(f'app/data/opinions/{product_id}.json', 'w', encoding='utf=8') as jf: #json file
                        json.dump(all_opinions, jf, indent=4, ensure_ascii=False)
                opinions = pd.DataFrame.from_dict(all_opinions)            
                opinions.rating = opinions.rating.apply(lambda rate: rate.split('/')[0].replace(',', '.')).astype(float)
                product = {
                    'product_id': product_id,
                    'product_name': product_name,
                    'opinions_count': len(opinions),
                    'pros_count': int(opinions.pros.astype(bool).sum()),
                    'cons_count': int(opinions.cons.astype(bool).sum()),
                    'avg_rating': round(opinions.rating.mean(), 1),
                    'rating_distribution': opinions.rating.value_counts().reindex(np.arange(0,5.2,0.5), fill_value = 0).to_dict(),
                    'recommendation_distribution' : opinions.recommendation.value_counts(dropna=False).reindex(['Polecam', 'Nie polecam', None]).to_dict()
                }
                if not os.path.exists('app/data/products'):
                    os.mkdir('app/data/products')
                with open(f'app/data/products/{product_id}.json', 'w', encoding='utf=8') as jf: #json file
                    json.dump(product, jf, indent=4, ensure_ascii=False)
                return redirect(url_for('product', product_id=product_id))
            return render_template('extract.html.jinja', error='Produkt o podanym kodzie nie ma opinii.')
        return render_template('extract.html.jinja', error='Produkt o podanym kodzie nie istnieje.')
    return render_template('extract.html.jinja')

@app.route('/products')
def products():
    product_list = [fname.split('.')[0] for fname in os.listdir('app/data/opinions')]
    products = []

    for product_id in product_list:
        with open(f'app/data/products/{product_id}.json', 'r', encoding='utf=8') as jf: #json file
            products.append(json.load(jf))

    return render_template('products.html.jinja', products=products)

@app.route('/author')
def author():
    return render_template('author.html.jinja')

@app.route('/product/<product_id>')
def product(product_id):
    opinions = {}
    prod_name = ''
    sort_by = request.args.get('sort', default='id')
    
    with open(f'app/data/products/{product_id}.json', 'r', encoding='utf=8') as jf: #json file
        tmp = json.load(jf)
        prod_name = tmp['product_name']
        
    with open(f'app/data/opinions/{product_id}.json', 'r', encoding='utf=8') as jf: #json file
        opinions = json.load(jf)
    
    if sort_by == 'id':
        opinions = sorted(opinions, key=lambda x: int(x['opinion_id']))
    elif sort_by == 'author':
        opinions = sorted(opinions, key=lambda x: x['author'])
    elif sort_by == 'recommendation':
        opinions = sorted(opinions, key=lambda x: x['recommendation'])
    elif sort_by == 'rating':
        opinions = sorted(opinions, key=lambda x: float(x['rating'].replace(',', '.').split('/')[0]), reverse=True)
    elif sort_by == 'content':
        opinions = sorted(opinions, key=lambda x: len(x['content']), reverse=True)
    elif sort_by == 'pros':
        opinions = sorted(opinions, key=lambda x: len(x['pros']), reverse=True)
    elif sort_by == 'cons':
        opinions = sorted(opinions, key=lambda x: len(x['cons']), reverse=True)
    elif sort_by == 'useful':
        opinions = sorted(opinions, key=lambda x: int(x['useful']), reverse=True)
    elif sort_by == 'useless':
        opinions = sorted(opinions, key=lambda x: int(x['useless']), reverse=True)
    elif sort_by == 'publish-date':
        opinions = sorted(opinions, key=lambda x: datetime.strptime(x['publish_date'], '%Y-%m-%d %H:%M:%S'))
    elif sort_by == 'purchase-date':
        opinions = sorted(opinions, key=lambda x: datetime.strptime(x['purchase_date'], '%Y-%m-%d %H:%M:%S'))
    
    return render_template('product.html.jinja', opinions=opinions, prod_name=prod_name, product_id=product_id)

@app.route('/product/download_json/<product_id>')
def download_json(product_id):
    return send_file(f'data/opinions/{product_id}.json', 'text/json', as_attachment=True)

@app.route('/product/download_csv/<product_id>')
def download_csv(product_id):
    opinions = pd.read_json(f'app/data/opinions/{product_id}.json')
    buffer = io.BytesIO(opinions.to_csv(sep=';', decimal=',', index=False).encode())
    return send_file(buffer, 'text/csv', as_attachment=True, download_name=f'{product_id}.csv')

@app.route('/product/download_xlsx/<product_id>')
def download_xlsx(product_id):
    pass