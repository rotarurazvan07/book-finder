import { BrowserRouter, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import Catalog from './pages/Catalog';
import Recommendations from './pages/Recommendations';
import Insights from './pages/Insights';

export default function App() {
    return (
        <BrowserRouter>
            <Layout>
                <Routes>
                    <Route path="/" element={<Catalog />} />
                    <Route path="/recommendations" element={<Recommendations />} />
                    <Route path="/insights" element={<Insights />} />
                </Routes>
            </Layout>
        </BrowserRouter>
    );
}