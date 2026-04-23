declare module 'react';
declare module 'react-dom/client';
declare module 'react/jsx-runtime';
declare module './pages/LandingPage';
declare module './pages/UploadPage';
declare module './pages/ResultsPage';
declare module './pages/ExplainPage';
declare module './Spinner';

declare namespace JSX {
    interface IntrinsicElements {
        [elemName: string]: any;
    }
}
