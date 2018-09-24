import { Component, OnInit } from '@angular/core';
import { Http } from '@angular/http';
import { Search } from '../search';

@Component({
  selector: 'app-search-form',
  templateUrl: './search-form.component.html',
  styleUrls: ['./search-form.component.css']
})
export class SearchFormComponent implements OnInit {

  constructor(
  	public http: Http
  ) { 
    this.http.get('/get-latest-block')
    .subscribe((res: any) => {
      this.last_index = res.json().index
      this.result = [res.json()]
    },
    (err: any) => {
      alert('something went terribly wrong!')
    });  
  }

  ngOnInit() {
  }

  model = new Search('');
  result = [];
  resultType = '';
  balance = 0;
  searching = false;
  submitted = false;
  last_index = 0;

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

  // TODO: Remove this when we're done
  get diagnostic() { return JSON.stringify(this.model); }
}
