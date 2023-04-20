const path = require('path');
const MiniCssExtractPlugin = require("mini-css-extract-plugin");
const CssMinimizerPlugin = require("css-minimizer-webpack-plugin");

var APP_DIR = path.resolve(__dirname, './js-src');
var BUILD_DIR = path.resolve(__dirname, './app/static');

module.exports = {
    entry: path.resolve(APP_DIR, 'index.js'),
    devtool: 'inline-cheap-source-map',
    output: {
        filename: 'bundle.js',
        path: BUILD_DIR,
    },
    plugins: [
        new MiniCssExtractPlugin({
            filename: 'peddleweb.css',
        }),
    ],
    module: {
        rules: [
            {
                test: /\.css$/i,
                use: [
                    MiniCssExtractPlugin.loader,
                    {
                        loader: 'css-loader',
                        options: { url: false }
                    }
                ]
            },
            {
                test: /\.m?jsx?$/,
                exclude: /(node_modules|bower_components)/,
                use: {
                    loader: 'babel-loader',
                    options: {
                        presets: ['@babel/preset-react'],
                    }
                }
            }
        ]
    },
    optimization: {
        minimizer: [
            new CssMinimizerPlugin(),
        ]
    },
    externals: {
        'jquery': '$',
        'react': 'React',
        'react-dom': 'ReactDOM',
        'react-bootstrap': 'ReactBootstrap',
    },
    resolve: {
        extensions: ['', '.js', '.jsx']
    }
};