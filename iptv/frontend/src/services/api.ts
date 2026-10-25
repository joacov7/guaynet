import axios from "axios";

const client = axios.create({ baseURL: "/api/v1" });

client.interceptors.request.use((cfg) => {
  const token = localStorage.getItem("iptv_token");
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

client.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("iptv_token");
      localStorage.removeItem("iptv_role");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export interface Category {
  id: number;
  name: string;
  icon: string;
  order: number;
}

export interface Channel {
  id: number;
  name: string;
  logo_url: string;
  stream_url: string;
  category_id: number | null;
  is_active: boolean;
  order: number;
}

export interface User {
  id: number;
  username: string;
  role: string;
  is_active: boolean;
  access_code: string | null;
}

export interface MeResponse {
  id: number;
  username: string;
  role: string;
  is_active: boolean;
  access_code: string | null;
}

export const authApi = {
  login: (username: string, password: string) =>
    client.post<{ access_token: string }>("/auth/login", new URLSearchParams({ username, password })),
  loginCode: (code: string) =>
    client.post<{ access_token: string }>("/auth/code", { code }),
  me: () => client.get<MeResponse>("/auth/me"),
};

export const watchApi = {
  categories: () => client.get<Category[]>("/watch/categories"),
  channels: (params?: { category_id?: number; search?: string }) =>
    client.get<Channel[]>("/watch/channels", { params }),
};

export const adminApi = {
  // Categories
  listCategories: () => client.get<Category[]>("/admin/categories"),
  createCategory: (data: Partial<Category>) => client.post<Category>("/admin/categories", data),
  updateCategory: (id: number, data: Partial<Category>) => client.put<Category>(`/admin/categories/${id}`, data),
  deleteCategory: (id: number) => client.delete(`/admin/categories/${id}`),
  // Channels
  listChannels: (params?: { category_id?: number; search?: string }) =>
    client.get<Channel[]>("/admin/channels", { params }),
  createChannel: (data: Partial<Channel>) => client.post<Channel>("/admin/channels", data),
  updateChannel: (id: number, data: Partial<Channel>) => client.put<Channel>(`/admin/channels/${id}`, data),
  deleteChannel: (id: number) => client.delete(`/admin/channels/${id}`),
  // Import
  importFromUrl: (url: string) => client.post<{ imported: number }>("/admin/import/url", { url }),
  importFromFile: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return client.post<{ imported: number }>("/admin/import/file", fd);
  },
  // Users
  listUsers: () => client.get<User[]>("/admin/users"),
  createUser: (data: Partial<User> & { password?: string }) => client.post<User>("/admin/users", data),
  updateUser: (id: number, data: Partial<User>) => client.put<User>(`/admin/users/${id}`, data),
  deleteUser: (id: number) => client.delete(`/admin/users/${id}`),
  regenCode: (id: number) => client.post<User>(`/admin/users/${id}/regen-code`),
};
