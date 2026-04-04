import client from './client';
import type { ActiveFilters, BooksResponse, FiltersResponse } from '../types';

export async function fetchBooks(
    page: number,
    pageSize: number,
    filters: ActiveFilters,
): Promise<BooksResponse> {
    const params: Record<string, unknown> = {
        page,
        page_size: pageSize,
        sort_by: filters.sort_by,
        sort_dir: filters.sort_dir,
    };

    if (filters.search) params.search = filters.search;
    if (filters.categories.length) params.categories = filters.categories;
    if (filters.stores.length) params.stores = filters.stores;
    if (filters.min_rating > 0) params.min_rating = filters.min_rating;
    if (filters.min_price !== null) params.min_price = filters.min_price;
    if (filters.max_price !== null) params.max_price = filters.max_price;

    const res = await client.get<BooksResponse>('/books', {
        params,
        // axios serialises array params as ?categories=A&categories=B
        paramsSerializer: { indexes: null },
    });
    return res.data;
}

export async function fetchFilters(): Promise<FiltersResponse> {
    const res = await client.get<FiltersResponse>('/filters');
    return res.data;
}