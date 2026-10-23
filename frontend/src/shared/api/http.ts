import axios from "axios";

export const client = axios.create({
  baseURL: "/api",
  timeout: 15000,
  withCredentials: true,
});
