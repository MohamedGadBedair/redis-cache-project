from app.config import settings

def _key(*parts:object)->str:
    return ':'.join([settings.cach_prefix,settings.cach_version,*map(str,parts)])

def product_key(product_id:int)->str:
    return _key('product',product_id)

def product_list_key(page:int,limit:int)->str:
    return _key('porducts','list',f'page={page}',f'limit={limit}')

def product_list_pattern()->str:
    return _key('products','list','*')