import { Component, OnInit } from '@angular/core';
import { Http } from '@angular/http';
import { Search } from '../search';

@Component({
  selector: 'app-search-form',
  templateUrl: './search-form.component.html',
  styleUrls: ['./search-form.component.css']
})
export class SearchFormComponent implements OnInit {

  model = new Search('');
  result = [];
  resultType = '';
  balance = 0;
  searching = false;
  submitted = false;
  current_height = '';
  circulating = '';
  hashrate = '';
  difficulty = '';

  constructor(
  	public http: Http
  ) { 
    this.http.get('/api-stats')
    .subscribe((res: any) => {
      this.difficulty = this.numberWithCommas(res.json()['stats']['difficulty']);
      this.hashrate = this.numberWithCommas(res.json()['stats']['network_hash_rate']);
      this.current_height = this.numberWithCommas(res.json()['stats']['height']);
      this.circulating = this.numberWithCommas(res.json()['stats']['circulating']);
      if (!window.location.search) {
        this.http.get('/explorer-search?term=' + this.current_height.replace(',', ''))
        .subscribe((res: any) => {
          this.result = res.json().result || []
          this.resultType = res.json().resultType
          this.balance = res.json().balance
          this.searching = false;
        },
        (err: any) => {
          alert('something went terribly wrong!')
        });
      }
    },
    (err: any) => {
      alert('something went terribly wrong!')
    });  
    if (window.location.search) {
      this.searching = true;
      this.submitted = true;
      this.http.get('/explorer-search' + window.location.search)
      .subscribe((res: any) => {
        this.result = res.json().result || []
        this.resultType = res.json().resultType
        this.balance = res.json().balance
        this.searching = false;
      },
      (err: any) => {
        alert('something went terribly wrong!')
      });
    }  
  }

  ngOnInit() {
  }

  onSubmit() { 
    this.searching = true;
  	this.submitted = true;
  	this.http.get('/explorer-search?term=' + encodeURIComponent(this.model.term))
  	.subscribe((res: any) => {
  		this.result = res.json().result || []
  		this.resultType = res.json().resultType
      this.balance = res.json().balance
      this.searching = false;
  	},
  	(err: any) => {
  		alert('something went terribly wrong!')
  	});	
  }

  numberWithCommas(x) {
    return x.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  }

  // TODO: Remove this when we're done
  get diagnostic() { return JSON.stringify(this.model); }
}
