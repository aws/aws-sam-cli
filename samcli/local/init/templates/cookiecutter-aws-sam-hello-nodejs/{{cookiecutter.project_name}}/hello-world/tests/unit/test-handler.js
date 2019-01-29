'use strict';

const app = require('../../app.js');
const chai = require('chai');
const expect = chai.expect;
var event, context;

describe('Tests index', function () {
    let result;
    before( async () => {
        result = await app.lambdaHandler(event, context);
    });
    
    describe('result', () => {
        it('is an object', () => {  
            expect(result).to.be.an('object');
        });
        it('is a successful request', () => { 
            expect(result.statusCode).to.equal(200);
        });
        it('has a string as result body', () => { 
            expect(result.body).to.be.an('string');
        });
    })

    describe('result.body', ()=> {
        let body; 
        before(() => {
            body = JSON.parse(result.body);
        })
        it('parses to object', () => {
            expect(body).to.be.an('object');
        });
        it('message is hello world', () => {
            expect(body.message).to.be.equal('hello world');
        });
        it('location is a string', () => { 
            expect(body.location).to.be.an('string');
        });
    });
});

